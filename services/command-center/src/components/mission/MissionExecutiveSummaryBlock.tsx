import type { ExecutiveMissionSummary } from "../../lib/missionExecutiveSummary";
import { formatRelativeTime } from "../../lib/format";

type Variant = "detail" | "panel" | "card";

export function MissionExecutiveSummaryBlock({
  summary,
  variant,
}: {
  summary: ExecutiveMissionSummary;
  variant: Variant;
}) {
  const dense = variant === "card";
  const labelCls = dense
    ? "text-[9px] font-semibold uppercase tracking-wider text-[var(--text-muted)]"
    : "text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]";
  const rowCls = dense
    ? "text-[11px] leading-snug text-[var(--text-secondary)]"
    : "text-xs leading-relaxed text-[var(--text-secondary)]";

  const rows: { key: string; label: string; value: string | null; emphasize?: boolean }[] = [
    { key: "last", label: "Last signal", value: summary.lastEventLine, emphasize: true },
    { key: "block", label: "Blocker", value: summary.blockerLine, emphasize: true },
    { key: "recv", label: "Latest receipt", value: summary.latestReceiptLine },
    { key: "appr", label: "Governance", value: summary.pendingApprovalLine },
  ];

  const filled = rows.filter((r) => r.value);

  if (filled.length === 0 && !summary.isSparse) {
    return null;
  }

  return (
    <div
      className={
        variant === "card"
          ? "mt-3 border-t border-[var(--bg-border)] pt-3"
          : "rounded-xl border border-[var(--bg-border)] bg-[var(--bg-void)]/80 px-3 py-3"
      }
    >
      {variant !== "card" ? (
        <p className={`mb-2 ${labelCls}`}>Mission readout</p>
      ) : null}
      {summary.isSparse && filled.length === 0 ? (
        <p className={rowCls}>Awaiting first execution update</p>
      ) : (
        <ul className={`space-y-2 ${dense ? "" : ""}`}>
          {filled.map((r) => (
            <li key={r.key} className="grid grid-cols-[minmax(0,5.5rem)_1fr] gap-x-2 gap-y-0.5">
              <span className={`shrink-0 ${labelCls}`}>{r.label}</span>
              <span
                className={`min-w-0 ${rowCls} ${r.emphasize ? "text-[var(--text-primary)]" : ""}`}
              >
                {r.value}
              </span>
            </li>
          ))}
        </ul>
      )}
      {summary.lastEventAt && (variant === "detail" || variant === "panel") ? (
        <p className="mt-2 font-mono text-[10px] text-[var(--text-muted)]">
          Signal time {formatRelativeTime(summary.lastEventAt)}
        </p>
      ) : null}
    </div>
  );
}

/** Single prioritized line for dense surfaces (mission list cards, overview rows). */
export function ExecutiveMissionCardLine({
  summary,
  className,
}: {
  summary: ExecutiveMissionSummary;
  /** Extra Tailwind classes; default adds top margin for card layout. */
  className?: string;
}) {
  const line =
    summary.pendingApprovalLine ??
    summary.blockerLine ??
    summary.lastEventLine ??
    (summary.isSparse ? "Awaiting first execution update" : null);
  if (!line) return null;
  return (
    <p
      className={`line-clamp-2 text-[11px] leading-snug text-[var(--text-secondary)] ${className ?? "mt-2"}`}
    >
      {line}
    </p>
  );
}
