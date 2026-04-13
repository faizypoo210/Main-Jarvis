import { Link } from "react-router-dom";
import { useShellHealth } from "../../contexts/ShellHealthContext";
import { healthDotClass } from "../../lib/operatorHealth";
import type { HealthState } from "../../lib/types";

function Pill({
  label,
  micro,
  state,
  title,
}: {
  label: string;
  micro: string;
  state: HealthState;
  title: string;
}) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded border border-[var(--bg-border)] bg-[var(--bg-void)]/50 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide text-[var(--text-secondary)]"
      title={title}
    >
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${healthDotClass(state)}`} aria-hidden />
      <span className="text-[var(--text-muted)]">{label}</span>
      <span className="text-[var(--text-primary)]">{micro}</span>
    </span>
  );
}

/** Compact cluster for the left rail (desktop). */
export function ShellRuntimeRail() {
  const { summary } = useShellHealth();
  const { pills } = summary;

  return (
    <Link
      to="/system"
      className="group hidden w-full min-w-0 rounded-lg border border-transparent px-1 py-1.5 transition-colors hover:border-[var(--bg-border)] hover:bg-[var(--bg-elevated)]/40 md:block"
      title="Runtime snapshot — same signals as System Health (operations visibility, not process supervision). Click for details."
    >
      <p className="mb-1 hidden font-mono text-[9px] uppercase tracking-wider text-[var(--text-muted)] lg:block">
        Runtime
      </p>
      <div className="flex flex-wrap gap-1">
        <Pill label="API" micro={pills.cp.short} state={pills.cp.state} title="Control plane API (from /api/v1/system/health)" />
        <Pill label="SSE" micro={pills.sse.short} state={pills.sse.state} title="Browser live stream" />
        <Pill label="Wrk" micro={pills.wr.short} state={pills.wr.state} title="Worker registry snapshot" />
        <Pill
          label="HB"
          micro={pills.hb.short}
          state={pills.hb.state}
          title={
            pills.hb.openCount != null && pills.hb.openCount > 0
              ? `${pills.hb.openCount} open supervision finding(s)`
              : "Heartbeat supervision snapshot"
          }
        />
      </div>
    </Link>
  );
}

/** Replaces the old single green dot — glanceable cluster aligned with shell summary. */
export function ShellRuntimeHeaderPills() {
  const { summary } = useShellHealth();
  const { pills } = summary;

  return (
    <div className="flex flex-wrap items-center justify-end gap-1">
      <Pill label="API" micro={pills.cp.short} state={pills.cp.state} title="Control plane" />
      <Pill label="SSE" micro={pills.sse.short} state={pills.sse.state} title="Live stream" />
      <Pill label="Wrk" micro={pills.wr.short} state={pills.wr.state} title="Workers" />
      <Pill label="HB" micro={pills.hb.short} state={pills.hb.state} title="Supervision findings" />
    </div>
  );
}

/** Subtle strip when something needs attention (not a second System Health page). */
export function ShellRuntimeAttentionBar() {
  const { summary } = useShellHealth();
  if (summary.overall === "ok" || summary.bannerLines.length === 0) {
    return null;
  }

  const border =
    summary.overall === "critical"
      ? "border-[var(--status-red)]/35 bg-[var(--status-red)]/10"
      : "border-[var(--status-amber)]/35 bg-[var(--status-amber)]/10";

  return (
    <div
      className={`shrink-0 border-b px-3 py-2 md:px-5 ${border}`}
      role="status"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-0.5 text-[11px] leading-snug text-[var(--text-secondary)]">
          {summary.bannerLines.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2 text-[10px] font-medium">
          <Link to="/system" className="text-[var(--accent-blue)] underline-offset-2 hover:underline">
            System Health
          </Link>
          {(summary.pills.hb.openCount ?? 0) > 0 ? (
            <Link to="/activity" className="text-[var(--accent-blue)] underline-offset-2 hover:underline">
              Activity
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}
