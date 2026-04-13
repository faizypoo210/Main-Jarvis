import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/api";
import type { MemoryCreateBody, MemoryItemRead, MemoryPatchBody, MissionMemoryPromoteBody } from "../lib/types";
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

function parseTags(raw: string): string[] {
  return raw
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}

function tagsToInput(tags: string[] | undefined): string {
  return (tags ?? []).join(", ");
}

type Panel =
  | null
  | { kind: "create" }
  | { kind: "edit"; item: MemoryItemRead }
  | { kind: "promote" };

function ModalFrame({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="memory-modal-title"
      onClick={onClose}
    >
      <div
        className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)] p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <h2 id="memory-modal-title" className="text-sm font-semibold text-[var(--text-primary)]">
            {title}
          </h2>
          <button
            type="button"
            className="shrink-0 rounded px-2 py-1 text-[10px] text-[var(--text-muted)] hover:bg-[var(--bg-elevated)]/60 hover:text-[var(--text-primary)]"
            onClick={onClose}
          >
            Close
          </button>
        </div>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  );
}

const fieldClass =
  "w-full rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)] px-2 py-1.5 font-mono text-xs text-[var(--text-primary)]";
const labelClass = "block text-[10px] font-medium text-[var(--text-muted)]";

export function Memory() {
  const [counts, setCounts] = useState<Awaited<ReturnType<typeof api.getMemoryCounts>> | null>(null);
  const [items, setItems] = useState<MemoryItemRead[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [writeError, setWriteError] = useState<string | null>(null);
  const [writeHint, setWriteHint] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [memoryType, setMemoryType] = useState<string>("");
  const [status, setStatus] = useState<string>("active");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [panel, setPanel] = useState<Panel>(null);
  const [saving, setSaving] = useState(false);

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

  const runWrite = useCallback(
    async (fn: () => Promise<unknown>, success: string) => {
      setWriteError(null);
      setWriteHint(null);
      setSaving(true);
      try {
        await fn();
        setWriteHint(success);
        setPanel(null);
        await refresh();
      } catch (e: unknown) {
        setWriteError(e instanceof Error ? e.message : String(e));
      } finally {
        setSaving(false);
      }
    },
    [refresh]
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
      {writeError ? (
        <div
          className="shrink-0 border-b border-[var(--status-amber)]/30 bg-[var(--status-amber)]/10 px-4 py-2 text-center text-xs text-[var(--status-amber)] md:px-6"
          role="status"
        >
          {writeError}
        </div>
      ) : null}
      {writeHint ? (
        <div
          className="shrink-0 border-b border-emerald-500/20 bg-emerald-500/10 px-4 py-2 text-center text-xs text-emerald-200/90 md:px-6"
          role="status"
        >
          {writeHint}
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-6">
        <h1 className="font-display text-lg font-semibold text-[var(--text-primary)]">Memory</h1>
        <p className="mt-1 max-w-2xl text-xs leading-relaxed text-[var(--text-muted)]">{subtitle}</p>
        <p className="mt-1 max-w-2xl text-[10px] leading-relaxed text-[var(--text-muted)]">
          Edits are governed by control-plane auth (same as other operator actions).
        </p>

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
              className={fieldClass}
              placeholder="title / summary / content"
            />
          </label>
          <label className="flex min-w-[120px] flex-col gap-1 text-[10px] text-[var(--text-muted)]">
            Type
            <select
              value={memoryType}
              onChange={(e) => setMemoryType(e.target.value)}
              className={fieldClass}
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
              className={fieldClass}
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
          <button
            type="button"
            onClick={() => {
              setWriteError(null);
              setPanel({ kind: "create" });
            }}
            className="rounded-lg border border-[var(--accent-blue)]/40 bg-[var(--accent-blue)]/10 px-3 py-2 text-xs font-medium text-[var(--accent-blue)] hover:bg-[var(--accent-blue)]/20"
          >
            New memory
          </button>
          <button
            type="button"
            onClick={() => {
              setWriteError(null);
              setPanel({ kind: "promote" });
            }}
            className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-elevated)]/60 px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
          >
            Promote from mission
          </button>
        </div>

        <p className="mt-3 text-[10px] text-[var(--text-muted)]">
          Showing {items.length} of {total}
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
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  <time className="font-mono text-[10px] text-[var(--text-muted)]">
                    {formatRelativeTime(m.updated_at)} updated
                  </time>
                  <button
                    type="button"
                    className="rounded border border-[var(--bg-border)] px-2 py-1 text-[10px] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]/60"
                    onClick={() => {
                      setWriteError(null);
                      setPanel({ kind: "edit", item: m });
                    }}
                  >
                    Edit
                  </button>
                  {m.status === "active" ? (
                    <button
                      type="button"
                      disabled={saving}
                      className="rounded border border-[var(--bg-border)] px-2 py-1 text-[10px] text-[var(--text-muted)] hover:bg-[var(--bg-elevated)]/60 disabled:opacity-50"
                      onClick={() =>
                        void runWrite(
                          () => api.patchMemory(m.id, { status: "archived" }),
                          "Archived."
                        )
                      }
                    >
                      Archive
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={saving}
                      className="rounded border border-[var(--bg-border)] px-2 py-1 text-[10px] text-[var(--text-muted)] hover:bg-[var(--bg-elevated)]/60 disabled:opacity-50"
                      onClick={() =>
                        void runWrite(
                          () => api.patchMemory(m.id, { status: "active" }),
                          "Restored to active."
                        )
                      }
                    >
                      Restore
                    </button>
                  )}
                </div>
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

      {panel?.kind === "create" ? (
        <CreateMemoryModal
          saving={saving}
          onClose={() => setPanel(null)}
          onSubmit={(data) =>
            void runWrite(() => api.createMemory(data), "Memory created.")
          }
        />
      ) : null}
      {panel?.kind === "edit" ? (
        <EditMemoryModal
          item={panel.item}
          saving={saving}
          onClose={() => setPanel(null)}
          onSubmit={(id, patch) => void runWrite(() => api.patchMemory(id, patch), "Saved.")}
        />
      ) : null}
      {panel?.kind === "promote" ? (
        <PromoteMemoryModal
          saving={saving}
          onClose={() => setPanel(null)}
          onSubmit={(data) =>
            void runWrite(() => api.promoteMemoryFromMission(data), "Promoted from mission.")
          }
        />
      ) : null}
    </div>
  );
}

function CreateMemoryModal({
  saving,
  onClose,
  onSubmit,
}: {
  saving: boolean;
  onClose: () => void;
  onSubmit: (data: MemoryCreateBody) => void;
}) {
  const [memoryType, setMemoryType] = useState<(typeof MEMORY_TYPES)[number]>("operator");
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [content, setContent] = useState("");
  const [importance, setImportance] = useState(3);
  const [tags, setTags] = useState("");
  const [missionId, setMissionId] = useState("");

  return (
    <ModalFrame title="New memory" onClose={onClose}>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (!title.trim()) return;
          onSubmit({
            memory_type: memoryType,
            title: title.trim(),
            summary: summary.trim() || null,
            content: content.trim() || null,
            importance,
            tags: parseTags(tags),
            mission_id: missionId.trim() || null,
          });
        }}
      >
        <div>
          <label className={labelClass}>Type</label>
          <select
            className={`${fieldClass} mt-1`}
            value={memoryType}
            onChange={(e) => setMemoryType(e.target.value as (typeof MEMORY_TYPES)[number])}
          >
            {MEMORY_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass}>Title</label>
          <input
            className={`${fieldClass} mt-1`}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Short label"
            required
          />
        </div>
        <div>
          <label className={labelClass}>Summary</label>
          <textarea
            className={`${fieldClass} mt-1 min-h-[72px]`}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder="Optional"
          />
        </div>
        <div>
          <label className={labelClass}>Content</label>
          <textarea
            className={`${fieldClass} mt-1 min-h-[96px]`}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Optional detail"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>Importance (1–5)</label>
            <input
              type="number"
              min={1}
              max={5}
              className={`${fieldClass} mt-1`}
              value={importance}
              onChange={(e) => setImportance(Number(e.target.value))}
            />
          </div>
          <div>
            <label className={labelClass}>Mission ID (optional)</label>
            <input
              className={`${fieldClass} mt-1`}
              value={missionId}
              onChange={(e) => setMissionId(e.target.value)}
              placeholder="UUID — links timeline"
            />
          </div>
        </div>
        <div>
          <label className={labelClass}>Tags (comma-separated)</label>
          <input
            className={`${fieldClass} mt-1`}
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="e.g. client, infra"
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            className="rounded-lg border border-[var(--bg-border)] px-3 py-2 text-xs text-[var(--text-muted)]"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || !title.trim()}
            className="rounded-lg border border-[var(--accent-blue)]/50 bg-[var(--accent-blue)]/15 px-3 py-2 text-xs font-medium text-[var(--accent-blue)] disabled:opacity-50"
          >
            {saving ? "Saving…" : "Create"}
          </button>
        </div>
      </form>
    </ModalFrame>
  );
}

function EditMemoryModal({
  item,
  saving,
  onClose,
  onSubmit,
}: {
  item: MemoryItemRead;
  saving: boolean;
  onClose: () => void;
  onSubmit: (id: string, patch: MemoryPatchBody) => void;
}) {
  const [title, setTitle] = useState(item.title);
  const [summary, setSummary] = useState(item.summary ?? "");
  const [content, setContent] = useState(item.content ?? "");
  const [status, setStatus] = useState<"active" | "archived">(
    item.status === "archived" ? "archived" : "active"
  );
  const [importance, setImportance] = useState(item.importance);
  const [tags, setTags] = useState(tagsToInput(item.tags));

  return (
    <ModalFrame title="Edit memory" onClose={onClose}>
      <p className="mb-3 font-mono text-[10px] text-[var(--text-muted)]">
        {item.memory_type} · {item.id}
      </p>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (!title.trim()) return;
          onSubmit(item.id, {
            title: title.trim(),
            summary: summary.trim() || null,
            content: content.trim() || null,
            status,
            importance,
            tags: parseTags(tags),
          });
        }}
      >
        <div>
          <label className={labelClass}>Title</label>
          <input
            className={`${fieldClass} mt-1`}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
        </div>
        <div>
          <label className={labelClass}>Summary</label>
          <textarea
            className={`${fieldClass} mt-1 min-h-[72px]`}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
        </div>
        <div>
          <label className={labelClass}>Content</label>
          <textarea
            className={`${fieldClass} mt-1 min-h-[120px]`}
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>Status</label>
            <select
              className={`${fieldClass} mt-1`}
              value={status}
              onChange={(e) => setStatus(e.target.value as "active" | "archived")}
            >
              <option value="active">active</option>
              <option value="archived">archived</option>
            </select>
          </div>
          <div>
            <label className={labelClass}>Importance (1–5)</label>
            <input
              type="number"
              min={1}
              max={5}
              className={`${fieldClass} mt-1`}
              value={importance}
              onChange={(e) => setImportance(Number(e.target.value))}
            />
          </div>
        </div>
        <div>
          <label className={labelClass}>Tags (comma-separated)</label>
          <input className={`${fieldClass} mt-1`} value={tags} onChange={(e) => setTags(e.target.value)} />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            className="rounded-lg border border-[var(--bg-border)] px-3 py-2 text-xs text-[var(--text-muted)]"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || !title.trim()}
            className="rounded-lg border border-[var(--accent-blue)]/50 bg-[var(--accent-blue)]/15 px-3 py-2 text-xs font-medium text-[var(--accent-blue)] disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </ModalFrame>
  );
}

function PromoteMemoryModal({
  saving,
  onClose,
  onSubmit,
}: {
  saving: boolean;
  onClose: () => void;
  onSubmit: (data: MissionMemoryPromoteBody) => void;
}) {
  const [missionId, setMissionId] = useState("");
  const [memoryType, setMemoryType] = useState<(typeof MEMORY_TYPES)[number]>("operator");
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [content, setContent] = useState("");
  const [importance, setImportance] = useState(3);
  const [tags, setTags] = useState("");
  const [dedupeKey, setDedupeKey] = useState("");

  return (
    <ModalFrame title="Promote from mission" onClose={onClose}>
      <p className="mb-3 text-[10px] leading-relaxed text-[var(--text-muted)]">
        Creates a memory row tied to the mission. Operator-initiated only — nothing runs automatically.
      </p>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (!missionId.trim() || !title.trim()) return;
          onSubmit({
            mission_id: missionId.trim(),
            memory_type: memoryType,
            title: title.trim(),
            summary: summary.trim() || null,
            content: content.trim() || null,
            importance,
            tags: parseTags(tags),
            dedupe_key: dedupeKey.trim() || null,
          });
        }}
      >
        <div>
          <label className={labelClass}>Mission ID</label>
          <input
            className={`${fieldClass} mt-1`}
            value={missionId}
            onChange={(e) => setMissionId(e.target.value)}
            placeholder="UUID"
            required
          />
        </div>
        <div>
          <label className={labelClass}>Type</label>
          <select
            className={`${fieldClass} mt-1`}
            value={memoryType}
            onChange={(e) => setMemoryType(e.target.value as (typeof MEMORY_TYPES)[number])}
          >
            {MEMORY_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass}>Title</label>
          <input
            className={`${fieldClass} mt-1`}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
        </div>
        <div>
          <label className={labelClass}>Summary</label>
          <textarea
            className={`${fieldClass} mt-1 min-h-[64px]`}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
        </div>
        <div>
          <label className={labelClass}>Content</label>
          <textarea
            className={`${fieldClass} mt-1 min-h-[80px]`}
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>Importance</label>
            <input
              type="number"
              min={1}
              max={5}
              className={`${fieldClass} mt-1`}
              value={importance}
              onChange={(e) => setImportance(Number(e.target.value))}
            />
          </div>
          <div>
            <label className={labelClass}>Dedupe key (optional)</label>
            <input
              className={`${fieldClass} mt-1`}
              value={dedupeKey}
              onChange={(e) => setDedupeKey(e.target.value)}
            />
          </div>
        </div>
        <div>
          <label className={labelClass}>Tags</label>
          <input className={`${fieldClass} mt-1`} value={tags} onChange={(e) => setTags(e.target.value)} />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            className="rounded-lg border border-[var(--bg-border)] px-3 py-2 text-xs text-[var(--text-muted)]"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || !missionId.trim() || !title.trim()}
            className="rounded-lg border border-[var(--accent-blue)]/50 bg-[var(--accent-blue)]/15 px-3 py-2 text-xs font-medium text-[var(--accent-blue)] disabled:opacity-50"
          >
            {saving ? "Promoting…" : "Promote"}
          </button>
        </div>
      </form>
    </ModalFrame>
  );
}
