import { useMemo, useState } from "react";
import { useOperatorIntegrations } from "../hooks/useOperatorIntegrations";
import {
  connectionSourceLabel,
  filterIntegrationItems,
  integrationStatusBadgeClass,
  summarizeIntegrationItems,
  type IntegrationFilterTab,
} from "../lib/integrationPresentation";
import { formatRelativeTime } from "../lib/format";

const tabs: IntegrationFilterTab[] = ["all", "connected", "needs_auth", "not_configured"];

export function Integrations() {
  const { data, error, loading } = useOperatorIntegrations();
  const [tab, setTab] = useState<IntegrationFilterTab>("all");

  const filtered = useMemo(
    () => (data ? filterIntegrationItems(data.items, tab) : []),
    [data, tab]
  );

  const summary = useMemo(() => {
    if (!data) return null;
    if (tab === "all") return data.summary;
    return summarizeIntegrationItems(filtered);
  }, [data, tab, filtered]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      {error ? (
        <div
          className="shrink-0 border-b border-[var(--status-amber)]/30 bg-[var(--status-amber)]/10 px-4 py-2 text-center text-xs text-[var(--status-amber)] md:px-6"
          role="status"
        >
          {error}
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-6">
        <p className="mb-4 max-w-2xl text-xs leading-relaxed text-[var(--text-muted)]">
          Readiness and wiring for external tools. The control plane does{" "}
          <span className="text-[var(--text-secondary)]">not</span> store vendor OAuth tokens; many signals
          are machine-local or inferred from this deployment.
        </p>

        {summary ? (
          <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Tracked {tab === "all" ? "(all)" : "(filtered)"}
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">
                {summary.total}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Connected
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--status-green)]">
                {summary.connected}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Needs auth
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--status-amber)]">
                {summary.needs_auth}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Other / not connected
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">
                {summary.not_configured_or_unknown}
              </p>
              <p className="mt-1 text-[9px] text-[var(--text-muted)]">
                Includes unknown, not configured, configured-without-proof, degraded
              </p>
            </div>
          </div>
        ) : loading ? (
          <p className="mb-6 text-sm text-[var(--text-muted)]">Loading integrations…</p>
        ) : null}

        <div className="mb-4 flex flex-wrap gap-2 border-b border-[var(--bg-border)]/80 pb-3">
          {tabs.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                tab === t
                  ? "bg-[var(--accent-blue-glow)] text-[var(--accent-blue)]"
                  : "text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-secondary)]"
              }`}
            >
              {t === "all"
                ? "All"
                : t === "connected"
                  ? "Connected"
                  : t === "needs_auth"
                    ? "Needs auth"
                    : "Not connected / other"}
            </button>
          ))}
        </div>

        {data?.truth_notes?.length ? (
          <ul className="mb-6 space-y-1 rounded-lg border border-[var(--bg-border)]/80 bg-[var(--bg-void)]/50 px-3 py-2 text-[10px] leading-relaxed text-[var(--text-muted)]">
            {data.truth_notes.map((n) => (
              <li key={n}>• {n}</li>
            ))}
          </ul>
        ) : null}

        {!loading && filtered.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">No integrations in this filter.</p>
        ) : null}

        <ul className="space-y-3">
          {filtered.map((it) => (
            <li
              key={it.id}
              className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/50 p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h3 className="text-sm font-medium text-[var(--text-primary)]">{it.name}</h3>
                  <p className="mt-0.5 font-mono text-[10px] text-[var(--text-muted)]">
                    {it.kind} · {it.provider}
                  </p>
                </div>
                <span
                  className={`shrink-0 rounded border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${integrationStatusBadgeClass(it.status)}`}
                >
                  {it.status.replace(/_/g, " ")}
                </span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">{it.summary}</p>
              <p className="mt-2 text-xs font-medium text-[var(--text-primary)]">
                Next: <span className="font-normal text-[var(--text-secondary)]">{it.next_action}</span>
              </p>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-[var(--bg-border)]/60 pt-2 font-mono text-[9px] text-[var(--text-muted)]">
                <span>Source: {connectionSourceLabel(it.connection_source)}</span>
                {it.last_activity_at ? (
                  <span>Last activity: {formatRelativeTime(it.last_activity_at)}</span>
                ) : (
                  <span>Last activity: —</span>
                )}
                {it.last_checked_at ? (
                  <span>Snapshot: {formatRelativeTime(it.last_checked_at)}</span>
                ) : null}
              </div>
              {Object.keys(it.meta).length > 0 ? (
                <details className="mt-2 text-[10px] text-[var(--text-muted)]">
                  <summary className="cursor-pointer font-medium text-[var(--text-secondary)]">
                    Inspectable meta (no secrets)
                  </summary>
                  <pre className="mt-1 max-h-32 overflow-auto rounded border border-[var(--bg-border)]/60 bg-[var(--bg-void)]/40 p-2 font-mono text-[9px]">
                    {JSON.stringify(it.meta)}
                  </pre>
                </details>
              ) : null}
            </li>
          ))}
        </ul>

        {data ? (
          <p className="mt-6 font-mono text-[9px] text-[var(--text-muted)]">
            Generated {formatRelativeTime(data.generated_at)}
          </p>
        ) : null}
      </div>
    </div>
  );
}
