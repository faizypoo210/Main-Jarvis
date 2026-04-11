import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/api";
import type { MemoryItemRead } from "../lib/types";
import { formatRelativeTime } from "../lib/format";

const MEMORY_TYPES = [
  "operator",
  "project",
  "person",
  "system",
  "preference",
  "integration",
  "workflow",
] as const;

export function Memory() {
  const [counts, setCounts] = useState<Awaited<ReturnType<typeof api.getMemoryCounts>> | null>(null);
  const [items, setItems] = useState<MemoryItemRead[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [memoryType, setMemoryType] = useState<string>("");
  const [status, setStatus] = useState<string>("active");
  const [expanded, setExpanded] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const [c, list] = await Promise.all([
        api.getMemoryCounts(),
        api.getMemoryList({
          q: q.trim() || undefined,
          memory_type: memoryType || undefined,
          status: status || undefined,
          limit: 100,
          offset: 0,
        }),
      ]);
      setCounts(c);
      setItems(list.items);
      setTotal(list.total);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [q, memoryType, status]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const subtitle = useMemo(
    () =>
      "Durable operator context stored in the control plane — not mission logs, chat transcripts, or raw receipts.",
    []
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
        <h1 className="font-display text-lg font-semibold text-[var(--text-primary)]">Memory</h1>
        <p className="mt-1 max-w-2xl text-xs leading-relaxed text-[var(--text-muted)]">{subtitle}</p>

        {counts ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Active
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">
                {counts.active}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Archived
              </p>
              <p className="mt-1 font-mono text-xl font-semibold text-[var(--text-primary)]">
                {counts.archived}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-3 sm:col-span-2 lg:col-span-2">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                By type
              </p>
              <p className="mt-1 font-mono text-[11px] leading-relaxed text-[var(--text-secondary)]">
                {Object.entries(counts.by_type)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(" · ") || "—"}
              </p>
            </div>
          </div>
        ) : loading ? (
          <p className="mt-4 text-xs text-[var(--text-muted)]">Loading counts…</p>
        ) : null}

        <div className="mt-6 flex flex-wrap items-end gap-3 border-b border-[var(--bg-border)]/80 pb-4">
          <label className="flex min-w-[140px] flex-col gap-1 text-[10px] text-[var(--text-muted)]">
            Search
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void refresh()}
              className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)] px-2 py-1.5 font-mono text-xs text-[var(--text-primary)]"
              placeholder="title / summary / content"
            />
          </label>
          <label className="flex min-w-[120px] flex-col gap-1 text-[10px] text-[var(--text-muted)]">
            Type
            <select
              value={memoryType}
              onChange={(e) => setMemoryType(e.target.value)}
              className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)] px-2 py-1.5 font-mono text-xs text-[var(--text-primary)]"
            >
              <option value="">All</option>
              {MEMORY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="flex min-w-[100px] flex-col gap-1 text-[10px] text-[var(--text-muted)]">
            Status
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)] px-2 py-1.5 font-mono text-xs text-[var(--text-primary)]"
            >
              <option value="">All</option>
              <option value="active">active</option>
              <option value="archived">archived</option>
            </select>
          </label>
          <button
            type="button"
            onClick={() => void refresh()}
            className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-elevated)]/60 px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
          >
            Apply
          </button>
        </div>

        <p className="mt-3 text-[10px] text-[var(--text-muted)]">
          Showing {items.length} of {total} · API writes require control plane API key.
        </p>

        {loading && items.length === 0 ? (
          <p className="mt-6 text-sm text-[var(--text-muted)]">Loading…</p>
        ) : null}

        <ul className="mt-4 space-y-3">
          {items.map((m) => (
            <li
              key={m.id}
              className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/50 p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h2 className="text-sm font-medium text-[var(--text-primary)]">{m.title}</h2>
                  <p className="mt-1 font-mono text-[10px] text-[var(--text-muted)]">
                    {m.memory_type} · {m.status} · importance {m.importance} · {m.source_kind}
                    {m.source_mission_id ? (
                      <>
                        {" "}
                        · mission{" "}
                        <Link
                          className="text-[var(--accent-blue)] underline-offset-2 hover:underline"
                          to={`/missions/${encodeURIComponent(m.source_mission_id)}`}
                        >
                          {m.source_mission_id.slice(0, 8)}…
                        </Link>
                      </>
                    ) : null}
                  </p>
                </div>
                <time className="font-mono text-[10px] text-[var(--text-muted)]">
                  {formatRelativeTime(m.updated_at)} updated
                </time>
              </div>
              {m.summary ? (
                <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">{m.summary}</p>
              ) : null}
              {m.content && expanded === m.id ? (
                <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[10px] text-[var(--text-muted)]">
                  {m.content}
                </pre>
              ) : null}
              <div className="mt-2 flex flex-wrap gap-2">
                {(m.tags ?? []).length ? (
                  <span className="text-[10px] text-[var(--text-muted)]">
                    {(m.tags ?? []).map((t) => (
                      <span
                        key={t}
                        className="mr-1 rounded border border-[var(--bg-border)] px-1 py-0.5 font-mono"
                      >
                        {t}
                      </span>
                    ))}
                  </span>
                ) : null}
                {m.content ? (
                  <button
                    type="button"
                    className="text-[10px] text-[var(--accent-blue)] hover:underline"
                    onClick={() => setExpanded((x) => (x === m.id ? null : m.id))}
                  >
                    {expanded === m.id ? "Hide detail" : "Show detail"}
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>

        {items.length === 0 && !loading ? (
          <p className="mt-8 text-center text-sm text-[var(--text-muted)]">No memory rows match.</p>
        ) : null}
      </div>
    </div>
  );
}
