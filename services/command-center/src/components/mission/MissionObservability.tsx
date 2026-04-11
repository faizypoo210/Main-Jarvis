import type { StreamPhase } from "../../contexts/ControlPlaneLiveContext";
import type { MissionTimingModel } from "../../lib/missionTiming";
import { formatDurationHuman } from "../../lib/missionTiming";
import { formatRelativeTime } from "../../lib/format";
import type { Mission } from "../../lib/types";

/** Compact timing — derived from mission events + `updated_at`. */
export function MissionTimingStrip({
  timing,
  mission,
}: {
  timing: MissionTimingModel;
  mission: Mission;
}) {
  const hasApprovalPath = Boolean(timing.approvalRequestedAt);

  return (
    <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-void)]/50 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Timing</p>
      <dl className="mt-2 space-y-1.5 font-mono text-[11px] text-[var(--text-secondary)]">
        {hasApprovalPath ? (
          <>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <dt className="text-[var(--text-muted)]">Time to approval request</dt>
              <dd className="text-[var(--text-primary)]">{formatDurationHuman(timing.msToApprovalRequest)}</dd>
            </div>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <dt className="text-[var(--text-muted)]">Governance window</dt>
              <dd className="text-[var(--text-primary)]" title="Requested to resolved">
                {formatDurationHuman(timing.msGovernanceWindow)}
              </dd>
            </div>
          </>
        ) : null}
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <dt className="text-[var(--text-muted)]">Time to first execution result</dt>
          <dd className="text-[var(--text-primary)]" title={hasApprovalPath ? "After approval to first receipt" : "Created to first receipt"}>
            {formatDurationHuman(timing.msToFirstExecutionResult)}
          </dd>
        </div>
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-t border-[var(--bg-border)] pt-2">
          <dt className="text-[var(--text-muted)]">Last updated</dt>
          <dd className="text-[var(--text-secondary)]" title={mission.updated_at}>
            {formatRelativeTime(mission.updated_at)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

type HealthTone = "ok" | "warn" | "muted";

function toneClass(tone: HealthTone): string {
  if (tone === "ok") return "text-emerald-400/90";
  if (tone === "warn") return "text-[var(--status-amber)]/90";
  return "text-[var(--text-muted)]";
}

/**
 * Three signals: live channel, governance API, execution evidence (receipt or status; bundle errors surface here).
 */
export function MissionOperationalHealthRow({
  streamPhase,
  pendingError,
  bundleError,
  mission,
  hasReceipt,
}: {
  streamPhase: StreamPhase;
  pendingError: string | null;
  bundleError: string | null;
  mission: Mission | null;
  hasReceipt: boolean;
}) {
  const liveTone: HealthTone =
    streamPhase === "live" ? "ok" : streamPhase === "reconnecting" ? "warn" : "warn";
  const liveLabel =
    streamPhase === "live" ? "Live" : streamPhase === "reconnecting" ? "Reconnecting" : "Polling";

  const govTone: HealthTone = pendingError ? "warn" : "ok";
  const govLabel = pendingError ? "Degraded" : "OK";

  let execTone: HealthTone = "muted";
  let execLabel = "—";
  if (bundleError) {
    execTone = "warn";
    execLabel = "Degraded";
  } else if (mission) {
    if (hasReceipt) {
      execTone = "ok";
      execLabel = "Receipt";
    } else if (mission.status === "active" || mission.status === "pending") {
      execTone = "warn";
      execLabel = "Awaiting";
    } else if (mission.status === "complete") {
      execTone = "ok";
      execLabel = "Settled";
    } else if (mission.status === "failed" || mission.status === "blocked") {
      execTone = "warn";
      execLabel = "Settled";
    } else if (mission.status === "awaiting_approval") {
      execTone = "warn";
      execLabel = "Paused";
    }
  }

  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--bg-border)] pt-3 font-mono text-[10px] uppercase tracking-wider"
      role="status"
      aria-label="Operational health"
    >
      <span className="text-[var(--text-muted)]">Runtime</span>
      <span className={toneClass(liveTone)} title="SSE or polling">
        Updates {liveLabel}
      </span>
      <span aria-hidden className="text-[var(--bg-border)]">
        ·
      </span>
      <span className={toneClass(govTone)} title="Pending approvals list">
        Approvals {govLabel}
      </span>
      <span aria-hidden className="text-[var(--bg-border)]">
        ·
      </span>
      <span
        className={toneClass(execTone)}
        title="Receipt on timeline or mission outcome; bundle errors affect this row"
      >
        Execution {execLabel}
      </span>
    </div>
  );
}
