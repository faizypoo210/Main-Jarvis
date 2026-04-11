import type { ActivityFeedCategory } from "./types";

export type ActivityFilterTab =
  | "all"
  | "mission"
  | "approval"
  | "execution"
  | "failures"
  | "memory"
  | "heartbeat";

export function mapActivityFilterToQuery(tab: ActivityFilterTab): ActivityFeedCategory | undefined {
  if (tab === "all") return undefined;
  if (tab === "failures") return "attention";
  if (tab === "memory") return "memory";
  if (tab === "heartbeat") return "heartbeat";
  return tab;
}

export function activityFilterLabel(tab: ActivityFilterTab): string {
  switch (tab) {
    case "all":
      return "All";
    case "mission":
      return "Mission";
    case "approval":
      return "Approval";
    case "execution":
      return "Execution";
    case "failures":
      return "Failures / attention";
    case "memory":
      return "Memory";
    case "heartbeat":
      return "Heartbeat";
    default:
      return tab;
  }
}

export function categoryBadgeClass(category: string): string {
  switch (category) {
    case "mission":
      return "border-[var(--status-blue)]/40 text-[var(--status-blue)]";
    case "approval":
      return "border-[var(--status-amber)]/50 text-[var(--status-amber)]";
    case "execution":
      return "border-[var(--status-green)]/40 text-[var(--status-green)]";
    case "memory":
      return "border-[var(--accent-blue)]/35 text-[var(--accent-blue)]";
    case "heartbeat":
      return "border-[var(--status-amber)]/40 text-[var(--status-amber)]";
    default:
      return "border-[var(--bg-border)] text-[var(--text-muted)]";
  }
}

export function kindBadgeLabel(kind: string): string {
  if (kind === "mission_event") return "Mission";
  if (kind === "approval") return "Approval";
  if (kind === "receipt") return "Execution";
  if (kind === "memory") return "Memory";
  if (kind === "heartbeat") return "Heartbeat";
  return kind;
}
