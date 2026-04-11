/** Calm, operator-facing copy for degraded paths (no generic error spam). */

export const operatorCopy = {
  /** Overview triage row cues — presentation-only, derived from event/mission timestamps. */
  overviewFreshness: {
    new: "New",
    justUpdated: "Just updated",
    needsReview: "Needs review",
  },
  liveReconnecting: "Live updates reconnecting.",
  liveOfflinePolling: "Live stream offline — using periodic sync.",
  bundlePartial: "Mission state updated. Detailed output unavailable.",
  receiptNoSummaryFailed:
    "Execution failed before a receipt summary was available.",
  receiptNoSummary: "Receipt recorded without a summary.",
  approvalDecisionRecorded: "Approval decision recorded.",
  /** Short confirmation line (governance actions, post-deny hint). */
  approvalDecisionRecordedShort: "Decision recorded.",
  /** While POST /decision is in flight (includes refresh). */
  approvalRecording: "Recording decision…",
  /** Optional sub-line if a surface shows two beats (use sparingly). */
  approvalRefreshingState: "Refreshing mission state.",
  /** Shared across overview, thread, right panel, voice, and mission detail after a failed POST /decision. */
  approvalResolveFailed: "Could not record decision. Try again.",
  approvalDeniedBlocked: "Denied. Mission blocked.",
  missionFailedNoReceiptDetail: "Mission failed before detailed output arrived.",
  /** Latest execution evidence — active / non-terminal missions (does not imply “finished”). */
  latestResultHeadingActive: "Latest execution output",
  /** Terminal success — still evidence text, not a duplicate “complete” claim in the summary line. */
  latestResultHeadingComplete: "Latest result",
  /** Failed mission — last observable execution output (does not soften failure semantics). */
  latestResultHeadingFailed: "Last execution output",
  /** Mission readout / receipts table row label. */
  latestResultReadoutRowLabel: "Latest result",
  /** Mission detail — primary receipt card (executive-first). */
  receiptPrimaryBadge: "Newest receipt",
  receiptEarlierHeading: "Earlier receipts",
  receiptInspectPayload: "Inspect payload",
  /** Accessible name for latest-result links that jump to receipts on mission detail. */
  latestResultNavigateLabel: "Open latest execution receipt",
  /** Mission detail — governed action launcher intro (approval-gated; not immediate vendor mutation). */
  governedLauncherIntro:
    "Submitting creates a pending approval request for this mission. GitHub and Gmail change only after you approve the request elsewhere.",
} as const;
