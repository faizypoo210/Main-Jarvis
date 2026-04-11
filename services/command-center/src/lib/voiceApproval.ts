import type { Approval, Mission, MissionEvent } from "./types";

/** Pending approval for the shell-focused mission, if any (same data as pending list API). */
export function getFocusedPendingApproval(
  threadMissionId: string | null,
  pending: Approval[]
): Approval | undefined {
  const tid = threadMissionId?.trim();
  if (!tid) return undefined;
  return pending.find((a) => a.mission_id === tid && a.status === "pending");
}

/** Count of pending approvals on missions other than the focused one. */
export function countPendingElsewhere(
  threadMissionId: string | null,
  pending: Approval[]
): number {
  const tid = threadMissionId?.trim();
  return pending.filter((a) => a.status === "pending" && (!tid || a.mission_id !== tid)).length;
}

/**
 * After an approval resolves to approved, distinguish "still waiting for execution output"
 * vs "at least one receipt after that decision" — uses the same timeline as the rest of the UI.
 */
export function derivePostApprovalPhase(
  mission: Mission | null,
  events: MissionEvent[]
): "awaiting_result" | "resumed" | null {
  if (!mission || mission.status !== "active") return null;
  const sorted = [...events].sort((a, b) => {
    const t = a.created_at.localeCompare(b.created_at);
    if (t !== 0) return t;
    return a.id.localeCompare(b.id);
  });
  let lastApprovedIdx = -1;
  for (let i = sorted.length - 1; i >= 0; i--) {
    const ev = sorted[i];
    if (!ev || ev.event_type !== "approval_resolved") continue;
    const p = ev.payload as { decision?: string } | null;
    if (p?.decision === "approved") {
      lastApprovedIdx = i;
      break;
    }
  }
  if (lastApprovedIdx < 0) return null;
  const after = sorted.slice(lastApprovedIdx + 1);
  const hasReceiptAfter = after.some((e) => e.event_type === "receipt_recorded");
  return hasReceiptAfter ? "resumed" : "awaiting_result";
}
