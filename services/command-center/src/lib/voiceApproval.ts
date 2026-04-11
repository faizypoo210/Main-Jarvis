import type { Approval } from "./types";

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

