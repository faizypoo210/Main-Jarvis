import type { IntegrationHubSummary, OperatorIntegrationRow } from "./types";

export type IntegrationFilterTab = "all" | "connected" | "needs_auth" | "not_configured";

export function filterIntegrationItems(
  items: OperatorIntegrationRow[],
  tab: IntegrationFilterTab
): OperatorIntegrationRow[] {
  if (tab === "all") return items;
  if (tab === "connected") return items.filter((i) => i.status === "connected");
  if (tab === "needs_auth") return items.filter((i) => i.status === "needs_auth");
  return items.filter((i) => i.status !== "connected" && i.status !== "needs_auth");
}

export function summarizeIntegrationItems(items: OperatorIntegrationRow[]): IntegrationHubSummary {
  const connected = items.filter((i) => i.status === "connected").length;
  const needs_auth = items.filter((i) => i.status === "needs_auth").length;
  const not_configured_or_unknown = Math.max(0, items.length - connected - needs_auth);
  return {
    total: items.length,
    connected,
    needs_auth,
    not_configured_or_unknown,
  };
}

export function integrationStatusBadgeClass(status: string): string {
  switch (status) {
    case "connected":
      return "border-[var(--status-green)]/50 text-[var(--status-green)]";
    case "configured":
      return "border-[var(--status-blue)]/50 text-[var(--status-blue)]";
    case "needs_auth":
      return "border-[var(--status-amber)]/50 text-[var(--status-amber)]";
    case "degraded":
      return "border-[var(--status-red)]/50 text-[var(--status-red)]";
    case "not_configured":
      return "border-[var(--bg-border)] text-[var(--text-muted)]";
    default:
      return "border-[var(--bg-border)] text-[var(--text-muted)]";
  }
}

export function connectionSourceLabel(source: string): string {
  switch (source) {
    case "db":
      return "Control plane DB";
    case "machine_probe":
      return "Machine probe";
    case "inferred":
      return "Repo / docs inference";
    case "external_unknown":
      return "Not verified here";
    default:
      return source;
  }
}
