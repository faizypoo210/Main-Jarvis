import type { HealthState } from "./types";

export function healthDotClass(status: HealthState): string {
  switch (status) {
    case "healthy":
      return "bg-[var(--status-green)]";
    case "degraded":
      return "bg-[var(--status-amber)]";
    case "offline":
      return "bg-[var(--status-red)]";
    default:
      return "bg-[var(--text-muted)]";
  }
}

export function healthLabel(status: HealthState): string {
  switch (status) {
    case "healthy":
      return "Healthy";
    case "degraded":
      return "Degraded";
    case "offline":
      return "Offline";
    default:
      return "Unknown";
  }
}
