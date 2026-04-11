import { useCallback, useEffect, useMemo, useState } from "react";
import { getOperatorEvals } from "../lib/api";
import type { OperatorValueEvalsResponse } from "../lib/types";

function fmtSeconds(s: number | null | undefined): string {
  if (s == null || Number.isNaN(s)) return "—";
  if (s < 120) return `${Math.round(s)}s`;
  if (s < 7200) return `${(s / 60).toFixed(1)}m`;
  return `${(s / 3600).toFixed(1)}h`;
}

function fmtUsd(v: string | number): string {
  const n = typeof v === "string" ? Number(v) : v;
  if (n == null || Number.isNaN(n)) return "—";
  return n.toFixed(6);
}

const WINDOW_PRESETS = [
  { label: "24h", hours: 24 },
  { label: "72h", hours: 72 },
  { label: "7d", hours: 168 },
  { label: "14d", hours: 336 },
] as const;

export function Evals() {
  const [windowHours, setWindowHours] = useState(168);
  const [groupByDay, setGroupByDay] = useState(false);
  const [data, setData] = useState<OperatorValueEvalsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getOperatorEvals({
        window_hours: windowHours,
        group_by: groupByDay ? "day" : undefined,
      });
      setData(res);
    } catch (e: unknown) {
      setData(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [windowHours, groupByDay]);

  useEffect(() => {
    void load();
  }, [load]);

  const integ = data?.integration_metrics;
  const integTotal = useMemo(() => {
    if (!integ) return 0;
    return (
      integ.github_issue_created +
      integ.github_issue_failed +
      integ.github_pull_request_created +
      integ.github_pull_request_failed +
      integ.github_pull_request_merged +
      integ.github_pull_request_merge_failed +
      integ.gmail_draft_created +
      integ.gmail_draft_failed +
      integ.gmail_reply_draft_created +
      integ.gmail_reply_draft_failed +
      integ.gmail_draft_sent +
      integ.gmail_draft_send_failed
    );
  }, [integ]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="shrink-0 border-b border-[var(--bg-border)] px-4 py-3 md:px-6">
        <h1 className="font-display text-lg font-semibold text-[var(--text-primary)]">
          Operator value (evals v1)
        </h1>
        <p className="mt-1 max-w-3xl text-xs leading-relaxed text-[var(--text-muted)]">
          Operational signals from control-plane mission truth — receipts, events, approvals, heartbeat. Not model
          quality. Small samples and long windows are labeled honestly below.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {WINDOW_PRESETS.map((p) => (
            <button
              key={p.hours}
              type="button"
              onClick={() => setWindowHours(p.hours)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                windowHours === p.hours
                  ? "bg-[var(--accent-blue)]/20 text-[var(--accent-blue)]"
                  : "bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {p.label}
            </button>
          ))}
          <label className="ml-2 flex cursor-pointer items-center gap-2 text-xs text-[var(--text-secondary)]">
            <input
              type="checkbox"
              checked={groupByDay}
              onChange={(e) => setGroupByDay(e.target.checked)}
              className="rounded border-[var(--bg-border)]"
            />
            Daily rollup
          </label>
          <button
            type="button"
            onClick={() => void load()}
            className="ml-auto rounded-lg border border-[var(--bg-border)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
          >
            Refresh
          </button>
        </div>
      </div>

      {error ? (
        <div
          className="shrink-0 border-b border-[var(--status-amber)]/30 bg-[var(--status-amber)]/10 px-4 py-2 text-center text-xs text-[var(--status-amber)] md:px-6"
          role="status"
        >
          {error}
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-6">
        {loading && !data ? (
          <p className="text-sm text-[var(--text-muted)]">Loading…</p>
        ) : null}

        {data ? (
          <>
            <p className="mb-4 font-mono text-[10px] text-[var(--text-muted)]">
              Window {data.summary.window_start_utc} → {data.summary.window_end_utc} ({data.window_hours}h UTC) ·
              generated {data.generated_at}
            </p>

            <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard
                label="Missions created"
                value={data.mission_metrics.missions_created_in_window}
                hint="created_at in window"
              />
              <MetricCard
                label="Reached complete"
                value={data.mission_metrics.missions_reached_complete_in_window}
                hint="status=complete & updated in window"
              />
              <MetricCard
                label="Reached failed"
                value={data.mission_metrics.missions_reached_failed_in_window}
                hint="status=failed & updated in window"
              />
              <MetricCard
                label="Pending approvals"
                value={data.approval_metrics.pending_now}
                hint="current snapshot"
              />
            </div>

            <section className="mb-6">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Time to progress (missions created in window)
              </h2>
              <div className="grid gap-3 md:grid-cols-2">
                <LatencyCard
                  title="→ first receipt"
                  stats={data.mission_metrics.time_created_to_first_receipt}
                />
                <LatencyCard
                  title="→ first integration executed"
                  stats={data.mission_metrics.time_created_to_first_integration_executed}
                />
              </div>
            </section>

            <section className="mb-6">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Approvals
              </h2>
              <div className="mb-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="Requested"
                  value={data.approval_metrics.approvals_requested_in_window}
                  hint="created in window"
                />
                <MetricCard
                  label="Resolved"
                  value={data.approval_metrics.approvals_resolved_in_window}
                  hint="decided in window"
                />
                <MetricCard
                  label="Denied (events)"
                  value={data.approval_metrics.approvals_denied_in_window}
                  hint="approval_resolved denied"
                />
                <MetricCard
                  label="Turnaround median"
                  value={fmtSeconds(data.approval_metrics.turnaround_seconds.median_seconds)}
                  hint="resolved in window"
                />
              </div>
              <p className="text-[10px] text-[var(--text-muted)]">
                Pending age (now): &lt;1h {data.approval_metrics.pending_age_under_1h} · 1–24h{" "}
                {data.approval_metrics.pending_age_1h_to_24h} · &gt;24h{" "}
                {data.approval_metrics.pending_age_over_24h}
              </p>
            </section>

            <section className="mb-6">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Governed integrations (receipts in window)
              </h2>
              {integTotal === 0 ? (
                <p className="text-xs text-[var(--text-muted)]">No governed integration receipts in this window.</p>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-[var(--bg-border)]">
                  <table className="w-full min-w-[480px] text-left text-xs">
                    <thead className="bg-[var(--bg-elevated)] text-[10px] uppercase text-[var(--text-muted)]">
                      <tr>
                        <th className="px-3 py-2">Workflow</th>
                        <th className="px-3 py-2">Success</th>
                        <th className="px-3 py-2">Failed</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--bg-border)] text-[var(--text-secondary)]">
                      <tr>
                        <td className="px-3 py-2">GitHub create issue</td>
                        <td className="px-3 py-2 font-mono">{integ?.github_issue_created}</td>
                        <td className="px-3 py-2 font-mono">{integ?.github_issue_failed}</td>
                      </tr>
                      <tr>
                        <td className="px-3 py-2">GitHub draft PR</td>
                        <td className="px-3 py-2 font-mono">{integ?.github_pull_request_created}</td>
                        <td className="px-3 py-2 font-mono">{integ?.github_pull_request_failed}</td>
                      </tr>
                      <tr>
                        <td className="px-3 py-2">GitHub PR merge</td>
                        <td className="px-3 py-2 font-mono">{integ?.github_pull_request_merged}</td>
                        <td className="px-3 py-2 font-mono">{integ?.github_pull_request_merge_failed}</td>
                      </tr>
                      <tr>
                        <td className="px-3 py-2">Gmail create draft</td>
                        <td className="px-3 py-2 font-mono">{integ?.gmail_draft_created}</td>
                        <td className="px-3 py-2 font-mono">{integ?.gmail_draft_failed}</td>
                      </tr>
                      <tr>
                        <td className="px-3 py-2">Gmail reply draft (thread)</td>
                        <td className="px-3 py-2 font-mono">{integ?.gmail_reply_draft_created}</td>
                        <td className="px-3 py-2 font-mono">{integ?.gmail_reply_draft_failed}</td>
                      </tr>
                      <tr>
                        <td className="px-3 py-2">Gmail send draft</td>
                        <td className="px-3 py-2 font-mono">{integ?.gmail_draft_sent}</td>
                        <td className="px-3 py-2 font-mono">{integ?.gmail_draft_send_failed}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="mb-6">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Failure categories (integration + approvals)
              </h2>
              <p className="mb-2 text-[10px] text-[var(--text-muted)]">
                Integration rows: mapped from receipt <code className="font-mono">error_code</code>. Denied counts
                mission approval_resolved denied events.
              </p>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {(
                  [
                    ["missing_auth", data.failure_categories.missing_auth],
                    ["provider_http_error", data.failure_categories.provider_http_error],
                    ["validation_error", data.failure_categories.validation_error],
                    ["approval_denied", data.failure_categories.approval_denied],
                    ["timeout", data.failure_categories.timeout],
                    ["unknown", data.failure_categories.unknown],
                  ] as const
                ).map(([k, v]) => (
                  <div
                    key={k}
                    className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 px-3 py-2"
                  >
                    <p className="text-[10px] uppercase text-[var(--text-muted)]">{k}</p>
                    <p className="font-mono text-lg text-[var(--text-primary)]">{v}</p>
                  </div>
                ))}
              </div>
            </section>

            <section className="mb-6">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Worker registry (snapshot)
              </h2>
              <p className="mb-2 max-w-3xl text-[10px] leading-relaxed text-[var(--text-muted)]">
                Direct registrations and heartbeats from workers posting to the control plane. Stale threshold
                aligns with supervision <code className="font-mono">stale_worker</code> (same minutes as the Workers
                page).
              </p>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="Registered"
                  value={data.worker_registry_metrics.registered_total}
                  hint="snapshot"
                />
                <MetricCard
                  label="Fresh heartbeat"
                  value={data.worker_registry_metrics.healthy_heartbeat}
                  hint="within threshold"
                />
                <MetricCard
                  label="Stale / absent"
                  value={data.worker_registry_metrics.stale_or_absent}
                  hint="over threshold or no heartbeat"
                />
                <MetricCard
                  label="Stale threshold"
                  value={`${data.worker_registry_metrics.threshold_minutes}m`}
                  hint="supervision alignment"
                />
              </div>
            </section>

            <section className="mb-6">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Cost events (window)
              </h2>
              <p className="mb-2 max-w-3xl text-[10px] leading-relaxed text-[var(--text-muted)]">
                Rows in <code className="font-mono">cost_events</code> with{" "}
                <code className="font-mono">created_at</code> in the eval window. USD totals only where status and
                currency were stored; not receipt-volume inference.
              </p>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="Events in window"
                  value={data.cost_event_metrics.events_in_window}
                  hint="cost_events rows"
                />
                <MetricCard
                  label="Direct (count)"
                  value={data.cost_event_metrics.direct_count}
                  hint="cost_status=direct"
                />
                <MetricCard
                  label="Unknown cost"
                  value={data.cost_event_metrics.unknown_count}
                  hint="no USD in payload"
                />
                <MetricCard
                  label="Not applicable"
                  value={data.cost_event_metrics.not_applicable_count}
                  hint="e.g. GitHub/Gmail API"
                />
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <MetricCard
                  label="Sum direct USD"
                  value={fmtUsd(data.cost_event_metrics.direct_total_usd)}
                  hint="stored amounts only"
                />
                <MetricCard
                  label="Sum estimated USD"
                  value={fmtUsd(data.cost_event_metrics.estimated_total_usd)}
                  hint="explicit estimated_cost_usd"
                />
              </div>
              {Object.keys(data.cost_event_metrics.provider_breakdown).length > 0 ? (
                <p className="mt-2 text-[10px] text-[var(--text-secondary)]">
                  <span className="text-[var(--text-muted)]">By provider: </span>
                  {Object.entries(data.cost_event_metrics.provider_breakdown)
                    .map(([k, c]) => `${k} (${c})`)
                    .join(" · ")}
                </p>
              ) : null}
            </section>

            <section className="mb-6">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Cost guardrails (heartbeat)
              </h2>
              <p className="mb-2 max-w-3xl text-[10px] leading-relaxed text-[var(--text-muted)]">
                <code className="font-mono">cost_*</code> findings from env thresholds on{" "}
                <code className="font-mono">cost_events</code>; opened/resolved counts use the same eval window.
              </p>
              <div className="grid gap-3 sm:grid-cols-3">
                <MetricCard
                  label="Cost findings opened"
                  value={data.cost_guardrail_metrics.cost_findings_opened_in_window}
                  hint="first_seen in window"
                />
                <MetricCard
                  label="Cost findings resolved"
                  value={data.cost_guardrail_metrics.cost_findings_resolved_in_window}
                  hint="resolved_at in window"
                />
                <MetricCard
                  label="Open cost findings now"
                  value={data.cost_guardrail_metrics.open_cost_findings_now}
                  hint="snapshot"
                />
              </div>
            </section>

            <section className="mb-6">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Heartbeat
              </h2>
              <div className="mb-2 grid gap-3 sm:grid-cols-3">
                <MetricCard
                  label="Findings opened"
                  value={data.heartbeat_metrics.findings_first_seen_in_window}
                  hint="first_seen in window"
                />
                <MetricCard
                  label="Findings resolved"
                  value={data.heartbeat_metrics.findings_resolved_in_window}
                  hint="resolved_at in window"
                />
                <MetricCard
                  label="Open now"
                  value={data.heartbeat_metrics.open_findings_total}
                  hint="snapshot"
                />
              </div>
              {Object.keys(data.heartbeat_metrics.open_findings_by_finding_type).length > 0 ? (
                <div className="text-xs text-[var(--text-secondary)]">
                  <span className="text-[var(--text-muted)]">By type: </span>
                  {Object.entries(data.heartbeat_metrics.open_findings_by_finding_type)
                    .map(([t, c]) => `${t} (${c})`)
                    .join(" · ")}
                </div>
              ) : null}
            </section>

            <section className="mb-6">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Routing (routing_decided in window)
              </h2>
              <p className="mb-2 max-w-3xl text-[10px] leading-relaxed text-[var(--text-muted)]">
                Mission routing: classifier requested vs actual mission path (executor is OpenClaw-only). OpenClaw
                model target (local/cloud) is on execution receipts — see <code className="font-mono">docs/MODEL_LANES.md</code>.
              </p>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                <MetricCard
                  label="Events"
                  value={data.routing_metrics.routing_decided_events_in_window}
                  hint="mission_events"
                />
                <MetricCard
                  label="Lane match"
                  value={data.routing_metrics.requested_matches_actual_lane}
                  hint="requested=actual"
                />
                <MetricCard
                  label="Lane mismatch"
                  value={data.routing_metrics.requested_differs_actual_lane}
                  hint="requested≠actual"
                />
                <MetricCard
                  label="local_fast→gateway"
                  value={data.routing_metrics.local_fast_to_gateway_fallback}
                  hint="fallback_applied"
                />
                <MetricCard
                  label="Requested local_fast"
                  value={data.routing_metrics.requested_local_fast}
                  hint="classifier"
                />
                <MetricCard
                  label="Actual gateway path"
                  value={data.routing_metrics.routing_actual_gateway}
                  hint="mission executor"
                />
              </div>
            </section>

            {data.timeseries.length > 0 ? (
              <section className="mb-6">
                <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                  Daily rollup (UTC)
                </h2>
                <div className="overflow-x-auto rounded-xl border border-[var(--bg-border)]">
                  <table className="w-full min-w-[400px] text-left text-xs">
                    <thead className="bg-[var(--bg-elevated)] text-[10px] uppercase text-[var(--text-muted)]">
                      <tr>
                        <th className="px-3 py-2">Day</th>
                        <th className="px-3 py-2">Created</th>
                        <th className="px-3 py-2">Complete</th>
                        <th className="px-3 py-2">Failed</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--bg-border)] text-[var(--text-secondary)]">
                      {data.timeseries.map((row) => (
                        <tr key={row.day_utc}>
                          <td className="px-3 py-2 font-mono">{row.day_utc}</td>
                          <td className="px-3 py-2 font-mono">{row.missions_created}</td>
                          <td className="px-3 py-2 font-mono">{row.missions_reached_complete}</td>
                          <td className="px-3 py-2 font-mono">{row.missions_reached_failed}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            ) : null}

            <section className="mb-8 rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/40 p-4">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Data quality & definitions
              </h2>
              <ul className="list-inside list-disc space-y-1 text-[10px] text-[var(--text-muted)]">
                {data.data_quality.direct_from_store.map((s) => (
                  <li key={`d-${s.slice(0, 40)}`}>
                    <span className="text-[var(--text-secondary)]">Direct: </span>
                    {s}
                  </li>
                ))}
                {data.data_quality.derived_aggregates.map((s) => (
                  <li key={`v-${s.slice(0, 40)}`}>
                    <span className="text-[var(--text-secondary)]">Derived: </span>
                    {s}
                  </li>
                ))}
                {data.data_quality.caveats.map((s) => (
                  <li key={`c-${s.slice(0, 40)}`} className="text-[var(--status-amber)]">
                    {s}
                  </li>
                ))}
                {data.summary.notes.map((s) => (
                  <li key={`n-${s.slice(0, 40)}`}>{s}</li>
                ))}
              </ul>
              {Object.keys(data.mission_metrics.missions_by_status_for_created_cohort).length > 0 ? (
                <p className="mt-3 text-[10px] text-[var(--text-muted)]">
                  <span className="font-medium text-[var(--text-secondary)]">Created-cohort status (current): </span>
                  {Object.entries(data.mission_metrics.missions_by_status_for_created_cohort)
                    .map(([k, v]) => `${k}=${v}`)
                    .join(", ")}
                </p>
              ) : null}
            </section>
          </>
        ) : null}
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
      <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">{value}</p>
      {hint ? <p className="mt-1 text-[9px] text-[var(--text-muted)]">{hint}</p> : null}
    </div>
  );
}

function LatencyCard({
  title,
  stats,
}: {
  title: string;
  stats: OperatorValueEvalsResponse["mission_metrics"]["time_created_to_first_receipt"];
}) {
  return (
    <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
      <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">{title}</p>
      <p className="mt-1 font-mono text-sm text-[var(--text-primary)]">
        n={stats.sample_count} · median {fmtSeconds(stats.median_seconds)} · p90{" "}
        {fmtSeconds(stats.p90_seconds)}
      </p>
      <p className="mt-1 text-[9px] text-[var(--text-muted)]">
        min {fmtSeconds(stats.min_seconds)} · max {fmtSeconds(stats.max_seconds)}
      </p>
    </div>
  );
}
