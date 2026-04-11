import type { Mission, Receipt } from "./types";
import type { LatestExecutionResult } from "./missionLatestResult";
import { operatorCopy } from "./operatorCopy";

/**
 * Per-receipt presentation derived from persisted receipt rows only (bundle / API).
 * Not a second source of truth — same fields as mission detail receipts list.
 */
export type ReceiptPresentation = {
  receiptId: string;
  receiptType: string;
  source: string;
  createdAt: string;
  /** Non-empty summary text when present. */
  summaryPlain: string | null;
  emptySummaryFallback: string;
  executionMeta: unknown | null;
  payloadRecord: Record<string, unknown>;
};

export function deriveReceiptPresentation(mission: Mission, receipt: Receipt): ReceiptPresentation {
  const summary = receipt.summary?.trim() || null;
  const emptyFallback =
    mission.status === "failed" ? operatorCopy.receiptNoSummaryFailed : operatorCopy.receiptNoSummary;
  const raw =
    receipt.payload && typeof receipt.payload === "object" && !Array.isArray(receipt.payload)
      ? (receipt.payload as Record<string, unknown>)
      : {};
  const executionMeta = "execution_meta" in raw ? raw.execution_meta : null;
  return {
    receiptId: receipt.id,
    receiptType: receipt.receipt_type,
    source: receipt.source,
    createdAt: receipt.created_at,
    summaryPlain: summary,
    emptySummaryFallback: emptyFallback,
    executionMeta,
    payloadRecord: raw,
  };
}

export function sortReceiptsNewestFirst(receipts: Receipt[]): Receipt[] {
  return [...receipts].sort((a, b) => b.created_at.localeCompare(a.created_at));
}

/**
 * Primary receipt aligns with `deriveLatestExecutionResult` when the newest evidence is a receipt row;
 * otherwise the newest receipt row is still shown first (timeline may lead by one event).
 */
export function selectPrimaryReceipt(
  sortedNewestFirst: Receipt[],
  latest: LatestExecutionResult | null
): { primary: Receipt; older: Receipt[] } {
  if (sortedNewestFirst.length === 0) {
    throw new Error("selectPrimaryReceipt: empty list");
  }
  const rid = latest?.sourceReceiptId?.trim() ?? "";
  let primary: Receipt | undefined;
  if (rid) {
    primary = sortedNewestFirst.find((r) => r.id === rid);
  }
  if (!primary) {
    primary = sortedNewestFirst[0];
  }
  const older = sortedNewestFirst.filter((r) => r.id !== primary!.id);
  return { primary: primary!, older };
}

/** One-line preview for collapsed older rows. */
export function compactReceiptPreview(p: ReceiptPresentation, maxLen = 72): string {
  const t = (p.summaryPlain?.trim() || p.emptySummaryFallback).replace(/\s+/g, " ");
  if (t.length <= maxLen) return t;
  return `${t.slice(0, maxLen)}…`;
}
