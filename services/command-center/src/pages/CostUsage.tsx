import { useMemo } from "react";
import { useOperatorUsage } from "../hooks/useOperatorUsage";
import { formatRelativeTime } from "../lib/format";

function maxInSeries(values: number[]): number {
  if (values.length === 0) return 0;
  return Math.max(...values);
}

export function CostUsage() {
  const { data, error, loading } = useOperatorUsage();

  const maxDay = useMemo(
    () => maxInSeries((data?.receipts_by_day_utc ?? []).map((d) => d.count)),
    [data?.receipts_by_day_utc]
  );

  const laneTotal = useMemo(() => {
    const lanes = data?.lane_distribution ?? [];
    return lanes.reduce((a, x) => a + x.count, 0);
  }, [data?.lane_distribution]);

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
        <p className="mb-1 max-w-2xl text-xs leading-relaxed text-[var(--text-muted)]">
          <span className="text-[var(--text-secondary)]">Activity & execution usage</span> from control-plane
          missions and receipts. This is not token-level billing or exact cloud spend.
        </p>
        {data ? (
          <p className="mb-4 font-mono text-[10px] text-[var(--text-muted)]">
            Generated {formatRelativeTime(data.generated_at)}
          </p>
        ) : null}

        {loading && !data ? (
          <p className="text-sm text-[var(--text-muted)]">Loading usage snapshot…</p>
        ) : null}

        {data && data.missions_total === 0 && data.receipts_total === 0 ? (
          <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/40 px-4 py-8 text-center">
            <p className="text-sm text-[var(--text-muted)]">No missions or receipts in the database yet.</p>
            <p className="mt-2 text-xs text-[var(--text-muted)]">
              Run a rehearsal or live command — data will appear here.
            </p>
          </div>
        ) : null}

        {data && (data.missions_total > 0 || data.receipts_total > 0) ? (
          <div className="space-y-6">
            <section aria-labelledby="usage-summary">
              <h2
                id="usage-summary"
                className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]"
              >
                Volume
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-4">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                    Missions
                  </p>
                  <p className="mt-1 font-mono text-2xl font-semibold text-[var(--text-primary)]">
                    {data.missions_total}
                  </p>
                </div>
                <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-4">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                    Receipts
                  </p>
                  <p className="mt-1 font-mono text-2xl font-semibold text-[var(--text-primary)]">
                    {data.receipts_total}
                  </p>
                </div>
                <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-4">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                    OpenClaw executions
                  </p>
                  <p className="mt-1 font-mono text-2xl font-semibold text-[var(--text-primary)]">
                    {data.openclaw_execution_receipts}
                  </p>
                </div>
                <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-4">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                    Exec success / fail / unknown
                  </p>
                  <p className="mt-1 font-mono text-lg text-[var(--text-primary)]">
                    {data.openclaw_success} / {data.openclaw_failure} / {data.openclaw_success_unknown}
                  </p>
                  <p className="mt-1 text-[9px] text-[var(--text-muted)]">
                    From receipt payload <code className="font-mono">success</code> when present.
                  </p>
                </div>
              </div>
            </section>

            <section aria-labelledby="usage-missions">
              <h2
                id="usage-missions"
                className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]"
              >
                Missions by status
              </h2>
              <div className="overflow-hidden rounded-xl border border-[var(--bg-border)]">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-[var(--bg-border)] bg-[var(--bg-void)]/80">
                    <tr>
                      <th className="px-3 py-2 font-medium text-[var(--text-muted)]">Status</th>
                      <th className="px-3 py-2 font-medium text-[var(--text-muted)]">Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.missions_by_status.map((row) => (
                      <tr key={row.status} className="border-b border-[var(--bg-border)]/60 last:border-0">
                        <td className="px-3 py-2 font-mono text-[var(--text-secondary)]">{row.status}</td>
                        <td className="px-3 py-2 font-mono text-[var(--text-primary)]">{row.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section aria-labelledby="usage-lanes">
              <h2
                id="usage-lanes"
                className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]"
              >
                Execution lanes (OpenClaw receipts)
              </h2>
              {laneTotal === 0 ? (
                <p className="text-xs text-[var(--text-muted)]">No lane metadata on execution receipts yet.</p>
              ) : (
                <ul className="space-y-2">
                  {data.lane_distribution.map((lane) => {
                    const pct = Math.round((lane.count / laneTotal) * 100);
                    return (
                      <li key={lane.lane}>
                        <div className="flex items-center justify-between gap-2 text-xs">
                          <span className="font-mono text-[var(--text-secondary)]">{lane.lane}</span>
                          <span className="font-mono text-[var(--text-muted)]">
                            {lane.count} ({pct}%)
                          </span>
                        </div>
                        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--bg-border)]">
                          <div
                            className="h-full rounded-full bg-[var(--accent-blue)]/70"
                            style={{ width: `${Math.max(6, pct)}%` }}
                          />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section aria-labelledby="usage-days">
              <h2
                id="usage-days"
                className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]"
              >
                Receipt volume (UTC days, last 14 days)
              </h2>
              {data.receipts_by_day_utc.length === 0 ? (
                <p className="text-xs text-[var(--text-muted)]">No receipts in this window.</p>
              ) : (
                <ul className="space-y-2">
                  {data.receipts_by_day_utc.map((d) => {
                    const w = maxDay > 0 ? Math.round((d.count / maxDay) * 100) : 0;
                    return (
                      <li key={d.day}>
                        <div className="flex items-center justify-between gap-2 text-xs">
                          <span className="font-mono text-[var(--text-secondary)]">{d.day}</span>
                          <span className="font-mono text-[var(--text-muted)]">{d.count}</span>
                        </div>
                        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--bg-border)]">
                          <div
                            className="h-full rounded-full bg-[var(--status-blue)]/60"
                            style={{ width: `${Math.max(4, w)}%` }}
                          />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section aria-labelledby="usage-receipt-types">
              <h2
                id="usage-receipt-types"
                className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]"
              >
                Receipts by type
              </h2>
              <div className="overflow-hidden rounded-xl border border-[var(--bg-border)]">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-[var(--bg-border)] bg-[var(--bg-void)]/80">
                    <tr>
                      <th className="px-3 py-2 font-medium text-[var(--text-muted)]">Type</th>
                      <th className="px-3 py-2 font-medium text-[var(--text-muted)]">Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.receipts_by_type)
                      .sort((a, b) => b[1] - a[1])
                      .map(([k, v]) => (
                        <tr key={k} className="border-b border-[var(--bg-border)]/60 last:border-0">
                          <td className="px-3 py-2 font-mono text-[var(--text-secondary)]">{k}</td>
                          <td className="px-3 py-2 font-mono text-[var(--text-primary)]">{v}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        ) : null}
      </div>
    </div>
  );
}
