import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useOperatorInbox } from "../hooks/useOperatorInbox";
import { formatRelativeTime } from "../lib/format";
import type { InboxGroupTab, InboxStatusFilter, OperatorInboxItemRead } from "../lib/types";

const GROUP_TABS: { id: InboxGroupTab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "approvals", label: "Approvals" },
  { id: "system", label: "System" },
  { id: "cost", label: "Cost" },
  { id: "failures", label: "Failures" },
];

const STATUS_TABS: { id: InboxStatusFilter; label: string }[] = [
  { id: "open", label: "Open" },
  { id: "acknowledged", label: "Acknowledged" },
  { id: "snoozed", label: "Snoozed" },
  { id: "dismissed", label: "Dismissed" },
  { id: "all", label: "All" },
];

function severityBadgeClass(sev: string): string {
  if (sev === "urgent") {
    return "bg-[var(--status-red)]/15 text-[var(--status-red)] ring-1 ring-[var(--status-red)]/25";
  }
  if (sev === "attention") {
    return "bg-[var(--status-amber)]/15 text-[var(--status-amber)] ring-1 ring-[var(--status-amber)]/25";
  }
  return "bg-[var(--text-muted)]/10 text-[var(--text-muted)] ring-1 ring-[var(--bg-border)]";
}

function InboxRow({
  item,
  onAck,
  onSnooze,
  onDismiss,
  busyKey,
}: {
  item: OperatorInboxItemRead;
  onAck: (k: string) => void;
  onSnooze: (k: string, m: number) => void;
  onDismiss: (k: string) => void;
  busyKey: string | null;
}) {
  const busy = busyKey === item.item_key;
  return (
    <li
      className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/80 p-4 shadow-sm"
      style={{ backgroundColor: "var(--bg-surface)" }}
    >
      <div className="flex flex-wrap items-start gap-3">
        <span
          className={`shrink-0 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${severityBadgeClass(item.severity)}`}
        >
          {item.severity}
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-medium text-[var(--text-primary)]">{item.headline}</p>
          <p className="text-sm leading-relaxed text-[var(--text-secondary)]">{item.summary}</p>
          <p className="text-[10px] text-[var(--text-muted)]">
            {item.source_kind}
            {item.inbox_group ? ` · ${item.inbox_group}` : ""} · {formatRelativeTime(item.created_at)}
            {item.status !== "open" ? ` · ${item.status}` : ""}
          </p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Link
          to={item.related_href}
          className="rounded-lg bg-[var(--accent-blue)]/15 px-3 py-1.5 text-xs font-medium text-[var(--accent-blue)] ring-1 ring-[var(--accent-blue)]/30 hover:bg-[var(--accent-blue)]/25"
        >
          {item.action_label}
        </Link>
        {item.status === "open" ? (
          <>
            <button
              type="button"
              disabled={busy}
              onClick={() => void onAck(item.item_key)}
              className="rounded-lg px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] ring-1 ring-[var(--bg-border)] hover:bg-[var(--bg-elevated)] disabled:opacity-50"
            >
              Acknowledge
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void onSnooze(item.item_key, 60)}
              className="rounded-lg px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] ring-1 ring-[var(--bg-border)] hover:bg-[var(--bg-elevated)] disabled:opacity-50"
            >
              Snooze 1h
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void onSnooze(item.item_key, 240)}
              className="rounded-lg px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] ring-1 ring-[var(--bg-border)] hover:bg-[var(--bg-elevated)] disabled:opacity-50"
            >
              Snooze 4h
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void onDismiss(item.item_key)}
              className="rounded-lg px-3 py-1.5 text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-secondary)] disabled:opacity-50"
            >
              Dismiss
            </button>
          </>
        ) : null}
      </div>
    </li>
  );
}

export function Inbox() {
  const [group, setGroup] = useState<InboxGroupTab>("all");
  const [status, setStatus] = useState<InboxStatusFilter>("open");
  const { data, error, loading, acknowledge, snooze, dismiss } = useOperatorInbox(group, status);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const counts = data?.counts;

  const wrap = useMemo(
    () =>
      async (fn: () => Promise<void>, key: string) => {
        try {
          setBusyKey(key);
          await fn();
        } finally {
          setBusyKey(null);
        }
      },
    []
  );

  const onAck = (k: string) => wrap(() => acknowledge(k), k);
  const onSnooze = (k: string, m: number) => wrap(() => snooze(k, m), k);
  const onDismiss = (k: string) => wrap(() => dismiss(k), k);

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
        <header className="mb-6 space-y-2">
          <h1 className="font-display text-xl font-semibold text-[var(--text-primary)]">Inbox</h1>
          <p className="max-w-2xl text-xs leading-relaxed text-[var(--text-muted)]">
            Actionable queue from governed control-plane truth (approvals, supervision findings, integration
            failures, terminal missions). This is not the Activity timeline — use it to triage and hand off to
            missions, approvals, cost, or system surfaces.
          </p>
        </header>

        {counts ? (
          <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">Urgent</p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--status-red)]">{counts.urgent}</p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Attention
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--status-amber)]">
                {counts.attention}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">Info</p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">{counts.info}</p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Approvals
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">
                {counts.approvals_pending}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Heartbeat open
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">
                {counts.heartbeat_open}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Cost alerts
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">
                {counts.cost_alerts}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Open total
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--accent-blue)]">
                {counts.total_visible}
              </p>
            </div>
          </div>
        ) : null}

        <div className="mb-4 flex flex-wrap gap-2">
          {GROUP_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setGroup(t.id)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium ring-1 transition-colors ${
                group === t.id
                  ? "bg-[var(--accent-blue)]/15 text-[var(--accent-blue)] ring-[var(--accent-blue)]/40"
                  : "text-[var(--text-secondary)] ring-[var(--bg-border)] hover:bg-[var(--bg-elevated)]"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="mb-6 flex flex-wrap gap-2 border-b border-[var(--bg-border)] pb-3">
          {STATUS_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setStatus(t.id)}
              className={`rounded-lg px-2.5 py-1 text-[11px] font-medium ${
                status === t.id
                  ? "text-[var(--accent-blue)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {loading && !data ? (
          <p className="text-sm text-[var(--text-muted)]">Loading inbox…</p>
        ) : null}

        {!loading && data && data.items.length === 0 ? (
          <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-void)]/40 px-4 py-8 text-center">
            <p className="text-sm text-[var(--text-secondary)]">Nothing in this view right now.</p>
            <p className="mt-2 text-xs text-[var(--text-muted)]">
              Resolved missions, approvals, and supervision findings leave the inbox automatically. Activity still
              holds the full timeline.
            </p>
          </div>
        ) : null}

        {data && data.items.length > 0 ? (
          <ul className="space-y-3">
            {data.items.map((item) => (
              <InboxRow
                key={item.item_key}
                item={item}
                onAck={onAck}
                onSnooze={onSnooze}
                onDismiss={onDismiss}
                busyKey={busyKey}
              />
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
