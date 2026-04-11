import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useOperatorActivity } from "../hooks/useOperatorActivity";
import {
  activityFilterLabel,
  categoryBadgeClass,
  kindBadgeLabel,
  type ActivityFilterTab,
} from "../lib/activityPresentation";
import { formatRelativeTime } from "../lib/format";

const filterTabs: ActivityFilterTab[] = [
  "all",
  "mission",
  "approval",
  "execution",
  "memory",
  "heartbeat",
  "failures",
];

export function Activity() {
  const [tab, setTab] = useState<ActivityFilterTab>("all");
  const { summary, items, nextBefore, error, loading, loadingMore, loadMore } = useOperatorActivity(tab);

  const streamNote = useMemo(
    () =>
      tab === "heartbeat"
        ? "Heartbeat tab shows open supervision findings from heartbeat_findings (deduped). Other tabs merge mission timeline events with heartbeat rows."
        : "This feed is built from stored mission_events in the control plane (plus receipt join for execution outcomes). It is not a raw log export.",
    [tab]
  );

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
          Governed operator timeline — approvals, mission lifecycle, and execution receipts in one place.
        </p>

        {summary ? (
          <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Items ({summary.window_hours}h window)
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">
                {summary.total_in_window}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Approvals
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">
                {summary.approvals_in_window}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Execution events
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">
                {summary.execution_in_window}
              </p>
              <p className="mt-1 text-[9px] text-[var(--text-muted)]">Receipt recorded events</p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Needs attention
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">
                {summary.attention_in_window}
              </p>
              <p className="mt-1 text-[9px] leading-snug text-[var(--text-muted)]">
                Denied approvals, blocked/failed missions, failed executions (when success is stored).
              </p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Memory events
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">
                {summary.memory_in_window ?? 0}
              </p>
              <p className="mt-1 text-[9px] text-[var(--text-muted)]">Saved / promoted / archived</p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Heartbeat open
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">
                {summary.heartbeat_open_total ?? 0}
              </p>
              <p className="mt-1 text-[9px] text-[var(--text-muted)]">Supervision findings (deduped)</p>
            </div>
          </div>
        ) : loading ? (
          <p className="mb-6 text-sm text-[var(--text-muted)]">Loading summary…</p>
        ) : null}

        <div className="mb-4 flex flex-wrap gap-2 border-b border-[var(--bg-border)]/80 pb-3">
          {filterTabs.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setTab(f)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                tab === f
                  ? "bg-[var(--accent-blue-glow)] text-[var(--accent-blue)]"
                  : "text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-secondary)]"
              }`}
            >
              {activityFilterLabel(f)}
            </button>
          ))}
        </div>

        {loading && items.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">Loading activity…</p>
        ) : null}

        {!loading && items.length === 0 ? (
          <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/40 px-4 py-10 text-center">
            <p className="text-sm text-[var(--text-muted)]">No activity in this view yet.</p>
            <p className="mt-2 text-xs text-[var(--text-muted)]">
              Commands and rehearsals will produce mission events here — nothing is invented client-side.
            </p>
          </div>
        ) : null}

        <ul className="space-y-3">
          {items.map((it) => (
            <li
              key={it.id}
              className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/50 p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <span
                    className={`rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide ${categoryBadgeClass(it.category)}`}
                  >
                    {it.category}
                  </span>
                  <span className="rounded border border-[var(--bg-border)] px-1.5 py-0.5 font-mono text-[9px] text-[var(--text-muted)]">
                    {kindBadgeLabel(it.kind)}
                  </span>
                  {it.risk_class ? (
                    <span className="font-mono text-[9px] text-[var(--status-amber)]">
                      risk {it.risk_class}
                    </span>
                  ) : null}
                </div>
                <time
                  className="shrink-0 font-mono text-[10px] text-[var(--text-muted)]"
                  dateTime={it.occurred_at}
                >
                  {formatRelativeTime(it.occurred_at)} ·{" "}
                  {new Date(it.occurred_at).toLocaleString(undefined, {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </time>
              </div>
              <h3 className="mt-2 text-sm font-medium text-[var(--text-primary)]">{it.title}</h3>
              <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">{it.summary}</p>
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-[var(--text-muted)]">
                {it.mission_id ? (
                  <Link
                    to={`/missions/${encodeURIComponent(it.mission_id)}`}
                    className="font-medium text-[var(--accent-blue)] underline-offset-2 hover:underline"
                  >
                    {it.mission_title}
                  </Link>
                ) : (
                  <span className="font-medium text-[var(--text-secondary)]">{it.mission_title}</span>
                )}
                {it.actor_label ? (
                  <span>
                    Actor: <span className="font-mono text-[var(--text-secondary)]">{it.actor_label}</span>
                  </span>
                ) : null}
                <span>
                  Status: <span className="font-mono text-[var(--text-secondary)]">{it.status}</span>
                </span>
              </div>
              {it.meta?.provenance === "heartbeat_finding" ? (
                <p className="mt-2 font-mono text-[9px] leading-relaxed text-[var(--text-muted)]">
                  Heartbeat finding · dedupe{" "}
                  <span className="text-[var(--text-secondary)]">
                    {typeof it.meta.dedupe_key === "string" ? it.meta.dedupe_key : "—"}
                  </span>
                  {typeof it.meta.provenance_note === "string" && it.meta.provenance_note.trim() ? (
                    <> · {it.meta.provenance_note}</>
                  ) : null}
                </p>
              ) : typeof it.meta?.event_type === "string" ? (
                <p className="mt-2 font-mono text-[9px] text-[var(--text-muted)]">
                  Stored event: {it.meta.event_type}
                  {typeof it.meta.provenance === "string" ? ` · ${it.meta.provenance}` : ""}
                </p>
              ) : null}
            </li>
          ))}
        </ul>

        {nextBefore ? (
          <div className="mt-6 flex justify-center">
            <button
              type="button"
              disabled={loadingMore}
              onClick={() => void loadMore()}
              className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)]/60 px-4 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)]/70 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loadingMore ? "Loading…" : "Load older"}
            </button>
          </div>
        ) : null}

        <p className="mt-8 max-w-2xl text-[10px] leading-relaxed text-[var(--text-muted)]">{streamNote}</p>
      </div>
    </div>
  );
}
