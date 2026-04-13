import { useMemo } from "react";
import { useControlPlaneLive } from "../hooks/useControlPlane";
import { useOperatorUsage } from "../hooks/useOperatorUsage";
import { useOperatorWorkers } from "../hooks/useOperatorWorkers";
import { useSystemHealth } from "../hooks/useSystemHealth";
import { formatRelativeTime } from "../lib/format";
import { healthDotClass, healthLabel } from "../lib/operatorHealth";
import { buildWorkerRows } from "../lib/workerOps";

function readinessTagClass(tag: string): string {
  if (tag === "Ready") return "text-emerald-500/90";
  if (tag === "Not ready") return "text-[var(--status-amber)]";
  if (tag === "Degraded") return "text-[var(--status-amber)]/85";
  return "text-[var(--text-muted)]";
}

export function Workers() {
  const live = useControlPlaneLive();
  const { data: health, error: healthErr, loading: healthLoading } = useSystemHealth();
  const { data: usage, error: usageErr, loading: usageLoading } = useOperatorUsage();
  const { data: workers, error: workersErr, loading: workersLoading } = useOperatorWorkers();

  const rows = useMemo(
    () => buildWorkerRows(live.streamPhase, live.streamError, usage, health, workers),
    [live.streamPhase, live.streamError, usage, health, workers]
  );

  const err = healthErr ?? usageErr ?? workersErr;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      {err ? (
        <div
          className="shrink-0 border-b border-[var(--status-amber)]/30 bg-[var(--status-amber)]/10 px-4 py-2 text-center text-xs text-[var(--status-amber)] md:px-6"
          role="status"
        >
          {err}
        </div>
      ) : null}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-6">
        <p className="mb-4 max-w-2xl text-xs leading-relaxed text-[var(--text-muted)]">
          Workers that call{" "}
          <code className="font-mono text-[10px]">POST /api/v1/workers/register</code> and{" "}
          <code className="font-mono text-[10px]">heartbeat</code> show{" "}
          <span className="font-medium text-[var(--text-secondary)]">direct</span> last heartbeat from
          the registry. Coordinator / executor rows fall back to inferred timestamps only when no registry
          row exists.
        </p>
        {healthLoading && usageLoading && workersLoading ? (
          <p className="text-sm text-[var(--text-muted)]">Loading…</p>
        ) : null}
        <ul className="space-y-3">
          {rows.map((r) => (
            <li
              key={r.id}
              className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h3 className="text-sm font-medium text-[var(--text-primary)]">{r.title}</h3>
                <span className="flex shrink-0 items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full ${healthDotClass(r.status)}`} aria-hidden />
                  <span className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                    {healthLabel(r.status)}
                  </span>
                </span>
              </div>
              <p className="mt-1 text-[11px] leading-snug text-[var(--text-muted)]">{r.detail}</p>
              {r.readinessTag ? (
                <p className="mt-2 text-[10px] leading-snug text-[var(--text-secondary)]">
                  <span className="font-medium text-[var(--text-primary)]">Readiness </span>
                  <span className={`font-semibold ${readinessTagClass(r.readinessTag)}`}>
                    {r.readinessTag}
                  </span>
                  {r.readinessDetail ? (
                    <span className="mt-0.5 block font-normal text-[var(--text-muted)]">
                      {r.readinessDetail}
                    </span>
                  ) : null}
                </p>
              ) : null}
              <p className="mt-2 text-[10px] leading-snug text-[var(--text-secondary)]">{r.evidence}</p>
              {r.lastActivityLabel ? (
                <p className="mt-2 font-mono text-[10px] text-[var(--text-muted)]">
                  {r.lastActivityLabel}
                  {health?.checked_at && r.id !== "sse" ? (
                    <span className="ml-2">
                      · snapshot {formatRelativeTime(health.checked_at)}
                    </span>
                  ) : null}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
