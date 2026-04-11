import { Link } from "react-router-dom";
import type { LatestExecutionResult } from "../../lib/missionLatestResult";
import { formatRelativeTime } from "../../lib/format";
import { operatorCopy } from "../../lib/operatorCopy";

/** Compact scan line for headers and rails — only when `latest.hasResult`. */
export function LatestExecutionResultLine({
  latest,
  className,
  dense,
  to,
  ariaLabel = operatorCopy.latestResultNavigateLabel,
  onNavigate,
}: {
  latest: LatestExecutionResult;
  className?: string;
  /** Tighter type for overview triage rows. */
  dense?: boolean;
  /** When set, entire block is a calm navigation control (full path or `#fragment` for same page). */
  to?: string;
  ariaLabel?: string;
  /** Shell / thread handoff (e.g. `setThreadMissionId`) — runs before navigation. */
  onNavigate?: () => void;
}) {
  if (!latest.hasResult || !latest.resultSummary) return null;

  const labelCls = dense
    ? "text-[9px] font-semibold uppercase tracking-wide text-[var(--text-muted)]"
    : "text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)]";
  const bodyCls = dense
    ? "text-[10px] leading-snug text-[var(--text-secondary)]"
    : "text-xs leading-snug text-[var(--text-secondary)]";
  const timeCls = dense ? "font-mono text-[9px] text-[var(--text-muted)]" : "font-mono text-[10px] text-[var(--text-muted)]";

  const linkSurface =
    "rounded-md transition-colors duration-150 hover:bg-[var(--bg-elevated)]/50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-blue)]/35";

  const inner = (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5">
        <span className={labelCls}>{latest.resultLabel}</span>
        {latest.resultTimestamp ? (
          <span className={timeCls}>{formatRelativeTime(latest.resultTimestamp)}</span>
        ) : null}
      </div>
      <p className={`mt-0.5 line-clamp-2 ${bodyCls}`}>{latest.resultSummary}</p>
    </>
  );

  if (to) {
    if (to.startsWith("#")) {
      return (
        <a
          href={to}
          className={`block ${linkSurface} ${className ?? ""}`}
          aria-label={ariaLabel}
          onClick={() => onNavigate?.()}
        >
          {inner}
        </a>
      );
    }
    return (
      <Link
        to={to}
        className={`block ${linkSurface} ${className ?? ""}`}
        aria-label={ariaLabel}
        onClick={() => onNavigate?.()}
      >
        {inner}
      </Link>
    );
  }

  return (
    <div className={className} role="status" aria-live="polite">
      {inner}
    </div>
  );
}
