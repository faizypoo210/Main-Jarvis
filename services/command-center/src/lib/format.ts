/** Display helpers for mission / mission list (no styling). */

import type { Mission } from "./types";

export type MissionStatus =
  | "pending"
  | "active"
  | "blocked"
  | "awaiting_approval"
  | "complete"
  | "failed";

export function normalizeMissionStatus(s: string): MissionStatus {
  const allowed: MissionStatus[] = [
    "pending",
    "active",
    "blocked",
    "awaiting_approval",
    "complete",
    "failed",
  ];
  return (allowed.includes(s as MissionStatus) ? s : "pending") as MissionStatus;
}

/** Prefer most recently updated active mission; else newest by created_at. */
export function selectFocusMission(missions: Mission[]): Mission | null {
  if (missions.length === 0) return null;
  const active = missions
    .filter((m) => m.status === "active")
    .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
  if (active.length > 0) return active[0] ?? null;
  const newest = [...missions].sort(
    (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)
  )[0];
  return newest ?? null;
}

export function formatCreatedByLabel(createdBy: string): string {
  const readable = createdBy.replace(/_/g, " ");
  return `by ${readable}`;
}

export function formatRelativeTime(iso: string): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const diffSec = Math.floor((Date.now() - t) / 1000);
  if (diffSec < 10) return "just now";
  if (diffSec < 60) return `${diffSec} seconds ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return diffMin === 1 ? "1 minute ago" : `${diffMin} minutes ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return diffHr === 1 ? "1 hour ago" : `${diffHr} hours ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return diffDay === 1 ? "1 day ago" : `${diffDay} days ago`;
  return new Date(iso).toLocaleDateString();
}
