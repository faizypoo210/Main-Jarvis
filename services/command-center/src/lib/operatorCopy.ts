/** Calm, operator-facing copy for degraded paths (no generic error spam). */

export const operatorCopy = {
  liveReconnecting: "Live updates reconnecting.",
  liveOfflinePolling: "Live stream offline — using periodic sync.",
  bundlePartial: "Mission state updated. Detailed output unavailable.",
  receiptNoSummaryFailed:
    "Execution failed before a receipt summary was available.",
  receiptNoSummary: "Receipt recorded without a summary.",
  approvalDecisionRecorded: "Approval decision recorded.",
  approvalExecutionResumed: "Approved. Execution resumed.",
  approvalDeniedBlocked: "Denied. Mission blocked.",
  missionFailedNoReceiptDetail: "Mission failed before detailed output arrived.",
} as const;
