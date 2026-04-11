import type { Approval, Mission, MissionEvent, Receipt } from "./types";
import { normalizeMissionStatus } from "./format";
import { operatorCopy } from "./operatorCopy";
import { deriveOperatorMissionPhase, hasExecutionEvidence } from "./missionPhase";

/**
 * Compact “newest execution evidence” view from receipts + receipt_recorded events only.
 * Presentation-only — not a parallel backend status; terminal completion still comes from mission.status.
 */
export type LatestExecutionResult = {
  hasResult: boolean;
  /** Calm heading: differs for active vs terminal complete vs failed. */
  resultLabel: string;
  /** Short snippet (summary text, may be empty-summary fallback). */
  resultSummary: string | null;
  resultTimestamp: string | null;
  /** Table-style line: receipt type · summary (aligned with prior `latestReceiptLine`). */
  resultDetailLine: string | null;
  /** When newest evidence is a receipt row (not a timeline-only receipt event edge). */
  sourceReceiptId: string | null;
};

function filterMissionReceipts(missionId: string, receipts: Receipt[] | null | undefined): Receipt[] {
  if (!receipts?.length) return [];
  return receipts.filter((r) => r.mission_id === missionId);
}

function receiptRecordedForMission(missionId: string, events: MissionEvent[]): MissionEvent[] {
  const ev = Array.isArray(events) ? events : [];
  return ev.filter((e) => e.event_type === "receipt_recorded" && e.mission_id === missionId);
}

function summaryFromEventPayload(p: Record<string, unknown> | null): string {
  if (!p) return "";
  return typeof p.summary === "string" ? p.summary.trim() : "";
}

function receiptTypeFromEventPayload(p: Record<string, unknown> | null): string {
  if (!p) return "Receipt";
  const t = typeof p.receipt_type === "string" ? p.receipt_type.trim() : "";
  return t || "Receipt";
}

function emptySummaryCopy(mission: Mission): string {
  return mission.status === "failed" ? operatorCopy.receiptNoSummaryFailed : operatorCopy.receiptNoSummary;
}

type Picked = {
  at: string;
  detailLine: string;
  summarySnippet: string;
  sourceReceiptId: string | null;
};

function pickFromReceiptRow(r: Receipt, mission: Mission): Picked {
  const sum = r.summary?.trim();
  const summarySnippet = sum ? sum.slice(0, 160) : emptySummaryCopy(mission);
  const detailLine = `${r.receipt_type} · ${summarySnippet.slice(0, 120)}`;
  return {
    at: r.created_at,
    detailLine,
    summarySnippet: summarySnippet.slice(0, 160),
    sourceReceiptId: r.id,
  };
}

function pickFromReceiptEvent(ev: MissionEvent, mission: Mission): Picked {
  const p = (ev.payload ?? null) as Record<string, unknown> | null;
  const sum = summaryFromEventPayload(p);
  const rt = receiptTypeFromEventPayload(p);
  const summarySnippet = sum ? sum.slice(0, 160) : emptySummaryCopy(mission);
  const detailLine = `${rt} · ${summarySnippet.slice(0, 120)}`;
  return {
    at: ev.created_at,
    detailLine,
    summarySnippet: summarySnippet.slice(0, 160),
    sourceReceiptId: null,
  };
}

function resultHeadingForMission(mission: Mission): string {
  const norm = normalizeMissionStatus(mission.status);
  if (norm === "complete") return operatorCopy.latestResultHeadingComplete;
  if (norm === "failed") return operatorCopy.latestResultHeadingFailed;
  return operatorCopy.latestResultHeadingActive;
}

/**
 * Prefer the newest receipt row or `receipt_recorded` event by `created_at`; on tie, prefer the receipt row.
 */
export function deriveLatestExecutionResult(
  mission: Mission | null | undefined,
  events: MissionEvent[] | null | undefined,
  receipts: Receipt[] | null | undefined
): LatestExecutionResult {
  const safeMission = mission && typeof mission.id === "string" && mission.id.trim() ? mission : null;
  const safeEvents = Array.isArray(events) ? events : [];
  if (!safeMission) {
    return {
      hasResult: false,
      resultLabel: operatorCopy.latestResultHeadingActive,
      resultSummary: null,
      resultTimestamp: null,
      resultDetailLine: null,
      sourceReceiptId: null,
    };
  }

  const missionId = safeMission.id;
  const label = resultHeadingForMission(safeMission);

  const rRows = filterMissionReceipts(missionId, receipts)
    .slice()
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  const rEvents = receiptRecordedForMission(missionId, safeEvents)
    .slice()
    .sort((a, b) => b.created_at.localeCompare(a.created_at));

  const topR = rRows[0] ?? null;
  const topE = rEvents[0] ?? null;

  let picked: Picked | null = null;

  if (topR && topE) {
    const cmp = topR.created_at.localeCompare(topE.created_at);
    if (cmp > 0) {
      picked = pickFromReceiptRow(topR, safeMission);
    } else if (cmp < 0) {
      picked = pickFromReceiptEvent(topE, safeMission);
    } else {
      picked = pickFromReceiptRow(topR, safeMission);
    }
  } else if (topR) {
    picked = pickFromReceiptRow(topR, safeMission);
  } else if (topE) {
    picked = pickFromReceiptEvent(topE, safeMission);
  }

  if (!picked) {
    return {
      hasResult: false,
      resultLabel: label,
      resultSummary: null,
      resultTimestamp: null,
      resultDetailLine: null,
      sourceReceiptId: null,
    };
  }

  return {
    hasResult: true,
    resultLabel: label,
    resultSummary: picked.summarySnippet,
    resultTimestamp: picked.at,
    resultDetailLine: picked.detailLine,
    sourceReceiptId: picked.sourceReceiptId,
  };
}

/**
 * Mission list cards (Missions page): show compact latest-result preview when evidence exists and
 * the derived phase is not a “still warming / governance / pure executing” row — presentation-only.
 */
export function shouldShowMissionListLatestPreview(
  mission: Mission | null | undefined,
  events: MissionEvent[] | null | undefined,
  approvals: Approval[] | null | undefined,
  latest: LatestExecutionResult
): boolean {
  try {
    if (!mission?.id?.trim() || !latest?.hasResult || !latest.resultSummary?.trim()) return false;
    const ev = Array.isArray(events) ? events : [];
    const appr = Array.isArray(approvals) ? approvals : [];
    if (!hasExecutionEvidence(ev, null)) return false;

    const phase = deriveOperatorMissionPhase(mission, ev, appr, null).phase;

    if (phase === "awaiting_approval") return false;
    if (phase === "resumed_waiting_for_execution") return false;
    if (phase === "executing") return false;

    return true;
  } catch {
    return false;
  }
}

/** Stable fragment for the receipts block on mission detail (`#receipts`). */
export const MISSION_DETAIL_RECEIPTS_SECTION_ID = "receipts";

/** DOM id for a receipt anchor (`receipt-<uuid>`), used with `location.hash`. */
export function receiptAnchorDomId(receiptId: string): string {
  return `receipt-${receiptId.trim()}`;
}

/**
 * Mission detail URL with hash: exact receipt when `sourceReceiptId` is set, else receipts section top.
 * Presentation/navigation only — same ids as mission detail receipt anchors.
 */
export function missionDetailLatestResultHref(missionId: string, latest: LatestExecutionResult): string {
  if (!missionId?.trim()) return "/missions";
  const base = `/missions/${encodeURIComponent(missionId)}`;
  const frag = latest.sourceReceiptId?.trim()
    ? receiptAnchorDomId(latest.sourceReceiptId)
    : MISSION_DETAIL_RECEIPTS_SECTION_ID;
  return `${base}#${frag}`;
}

/** Same-page hash for in-mission links (header → receipts). */
export function missionDetailLatestResultHash(latest: LatestExecutionResult): string {
  const frag = latest.sourceReceiptId?.trim()
    ? receiptAnchorDomId(latest.sourceReceiptId)
    : MISSION_DETAIL_RECEIPTS_SECTION_ID;
  return `#${frag}`;
}
