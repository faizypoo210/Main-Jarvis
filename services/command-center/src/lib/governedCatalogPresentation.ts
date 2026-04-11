/**
 * Presentation helpers aligned with control-plane governed_action_catalog titles.
 * TRUTH_SOURCE: GET /api/v1/operator/action-catalog (approval_action_type ↔ title).
 */

import type { GovernedActionCatalogResponse } from "./types";

const TITLE_PREFIX = "Create approval request — ";

export function compactCatalogTitle(fullTitle: string): string {
  const t = fullTitle.trim();
  if (t.startsWith(TITLE_PREFIX)) {
    return t.slice(TITLE_PREFIX.length).trim();
  }
  return t || "Action";
}

export function labelForApprovalActionType(
  actionType: string | undefined,
  catalog: GovernedActionCatalogResponse | null
): string {
  const at = (actionType ?? "").trim();
  if (!at) return "Action";
  const row = catalog?.actions.find((a) => a.approval_action_type === at);
  if (row) return compactCatalogTitle(row.title);
  return at;
}

export function humanizeRequestedVia(v: string | undefined): string {
  const s = (v ?? "").trim().toLowerCase();
  if (s === "voice") return "Voice";
  if (s === "command_center") return "Command Center";
  if (s === "system") return "System";
  if (s === "sms") return "SMS";
  return (v ?? "").trim() || "—";
}

const GOVERNED_APPROVAL_TYPES = new Set([
  "github_create_issue",
  "github_create_pull_request",
  "github_merge_pull_request",
  "gmail_create_draft",
  "gmail_create_reply_draft",
  "gmail_send_draft",
]);

export function isGovernedApprovalActionType(actionType: string | undefined): boolean {
  const at = (actionType ?? "").trim();
  return GOVERNED_APPROVAL_TYPES.has(at);
}

/** Optional: mission timeline uses catalog-backed action names + humanized surfaces. */
export type GovernedTimelinePresentation = {
  labelForApprovalAction: (actionType: string) => string;
  humanizeVia: (via: string) => string;
};

export function buildGovernedTimelinePresentation(
  catalog: GovernedActionCatalogResponse | null
): GovernedTimelinePresentation {
  return {
    labelForApprovalAction: (at: string) => labelForApprovalActionType(at, catalog),
    humanizeVia: humanizeRequestedVia,
  };
}

export const HANDOFF_STORAGE_KEY = "jarvis.governed_handoff_v1";
