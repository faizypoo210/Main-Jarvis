import { useMemo } from "react";
import { Link } from "react-router-dom";
import { RiskBadge, type Risk } from "../common/RiskBadge";
import { StatusBadge } from "../common/StatusBadge";
import type { Mission } from "../../lib/types";
import { formatCreatedByLabel, formatRelativeTime, normalizeMissionStatus } from "../../lib/format";
import { useControlPlaneLive } from "../../hooks/useControlPlane";
import { deriveExecutiveMissionSummary, hasExecutiveCardLine } from "../../lib/missionExecutiveSummary";
import {
  deriveLatestExecutionResult,
  missionDetailLatestResultHref,
  shouldShowMissionListLatestPreview,
} from "../../lib/missionLatestResult";
import { deriveOperatorMissionPhase } from "../../lib/missionPhase";
import { useShellOutlet } from "../layout/AppShell";
import { ExecutiveMissionCardLine } from "../mission/MissionExecutiveSummaryBlock";
import { LatestExecutionResultLine } from "../mission/LatestExecutionResultLine";

function toRisk(r: string | null): Risk | null {
  if (r === "green" || r === "amber" || r === "red") return r;
  return null;
}

export function MissionCard({ mission }: { mission: Mission }) {
  const { setThreadMissionId } = useShellOutlet();
  const live = useControlPlaneLive();
  const events = live.eventsByMissionId[mission.id] ?? [];
  const approvals = live.pendingApprovals;

  const desc = mission.description?.trim() || mission.summary?.trim() || "";
  const risk = toRisk(mission.risk_class);

  const executive = useMemo(
    () => deriveExecutiveMissionSummary(mission, events, approvals, null),
    [mission, events, approvals]
  );

  const latestExec = useMemo(
    () => deriveLatestExecutionResult(mission, events, null),
    [mission, events]
  );

  const showLatestPreview = useMemo(
    () => shouldShowMissionListLatestPreview(mission, events, approvals, latestExec),
    [mission, events, approvals, latestExec]
  );

  const phaseView = useMemo(
    () => deriveOperatorMissionPhase(mission, events, approvals, null),
    [mission, events, approvals]
  );
  const terminalLatestPreview =
    phaseView.phase === "complete" || phaseView.phase === "failed";

  return (
    <article
      className="rounded-xl border border-[var(--bg-border)] transition-colors duration-150 ease-linear hover:bg-[var(--bg-elevated)]/50"
      style={{ backgroundColor: "var(--bg-surface)" }}
    >
      <Link
        to={`/missions/${encodeURIComponent(mission.id)}`}
        onClick={() => setThreadMissionId(mission.id)}
        className="block p-4 pb-2"
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h3 className="font-display text-base font-semibold text-[var(--text-primary)]">{mission.title}</h3>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={normalizeMissionStatus(mission.status)} />
            {risk ? <RiskBadge risk={risk} /> : null}
          </div>
        </div>
        <ExecutiveMissionCardLine summary={executive} />
        {!hasExecutiveCardLine(executive) && desc ? (
          <p className="mt-2 line-clamp-2 text-sm text-[var(--text-secondary)]">{desc}</p>
        ) : null}
      </Link>
      {showLatestPreview ? (
        <LatestExecutionResultLine
          latest={latestExec}
          dense
          className={`border-t px-4 py-2 ${
            terminalLatestPreview ? "border-[var(--bg-border)]/40" : "border-[var(--bg-border)]/60"
          }`}
          to={missionDetailLatestResultHref(mission.id, latestExec)}
          onNavigate={() => setThreadMissionId(mission.id)}
        />
      ) : null}
      <Link
        to={`/missions/${encodeURIComponent(mission.id)}`}
        onClick={() => setThreadMissionId(mission.id)}
        className="block px-4 pb-4 pt-2"
      >
        <div className="flex flex-wrap gap-3 font-mono text-[10px] text-[var(--text-muted)]">
          <span>{formatCreatedByLabel(mission.created_by)}</span>
          <span>{formatRelativeTime(mission.created_at)}</span>
        </div>
      </Link>
    </article>
  );
}
