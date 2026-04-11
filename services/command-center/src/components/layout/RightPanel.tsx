import { useMemo } from "react";
import { useOutletContext } from "react-router-dom";
import { MoreHorizontal, Search } from "lucide-react";
import { useControlPlaneLive, usePendingApprovals, usePolledMissionDetail, useResolveApprovalAction } from "../../hooks/useControlPlane";
import { ApprovalCard } from "../approvals/ApprovalCard";
import { StatusBadge } from "../common/StatusBadge";
import type { Approval, Mission } from "../../lib/types";
import { formatRelativeTime, normalizeMissionStatus, selectFocusMission } from "../../lib/format";
import { deriveExecutiveMissionSummary } from "../../lib/missionExecutiveSummary";
import { deriveLatestExecutionResult, missionDetailLatestResultHref } from "../../lib/missionLatestResult";
import { LatestExecutionResultLine } from "../mission/LatestExecutionResultLine";
import { MissionExecutiveSummaryBlock } from "../mission/MissionExecutiveSummaryBlock";
import { LiveLinkIndicator } from "./LiveLinkIndicator";
import { operatorCopy } from "../../lib/operatorCopy";

type ShellOutletContext = {
  setThreadMissionId: (id: string | null) => void;
};

export function RightPanel({
  missions,
  missionsLoading,
  threadMissionId,
  onClose,
}: {
  missions: Mission[];
  missionsLoading: boolean;
  /** When set, panel follows this mission (same anchor as the conversation thread). */
  threadMissionId: string | null;
  onClose?: () => void;
}) {
  const { streamPhase } = useControlPlaneLive();
  const { setThreadMissionId } = useOutletContext<ShellOutletContext>();
  const { approvals, loading: approvalsLoading } = usePendingApprovals();
  const focusFromList = useMemo(() => selectFocusMission(missions), [missions]);
  const focusMissionId = useMemo(() => {
    const tid = threadMissionId?.trim();
    if (tid) return tid;
    return focusFromList?.id ?? null;
  }, [threadMissionId, focusFromList?.id]);

  const { mission, events, loading: detailLoading } = usePolledMissionDetail(focusMissionId, 5000);

  const displayMission = useMemo(() => {
    if (mission) return mission;
    const tid = threadMissionId?.trim();
    if (tid) {
      const fromList = missions.find((m) => m.id === tid);
      if (fromList) return fromList;
    }
    return focusFromList;
  }, [mission, threadMissionId, missions, focusFromList]);

  const pendingForMission = useMemo(() => {
    if (!displayMission) return [] as Approval[];
    return approvals.filter((a) => a.mission_id === displayMission.id && a.status === "pending");
  }, [approvals, displayMission]);

  const executiveSummary = useMemo(() => {
    if (!displayMission) return null;
    return deriveExecutiveMissionSummary(displayMission, events, approvals, null);
  }, [displayMission, events, approvals]);

  const latestExecution = useMemo(() => {
    if (!displayMission) return null;
    return deriveLatestExecutionResult(displayMission, events, null);
  }, [displayMission, events]);

  const activityEvents = useMemo(() => {
    const last = events.slice(-5);
    return [...last].reverse();
  }, [events]);

  const { resolve, resolvingApprovalId, resolveErrorApprovalId, recentlyResolvedDecisionFor } =
    useResolveApprovalAction();

  const panelLoading = missionsLoading || (displayMission != null && detailLoading && events.length === 0);

  return (
    <aside
      className="flex h-full w-full flex-col border-l border-[var(--bg-border)] lg:w-[320px] lg:shrink-0"
      style={{ backgroundColor: "var(--bg-surface)" }}
    >
      <div className="flex flex-col gap-1 border-b border-[var(--bg-border)] px-4 py-3">
        <div className="flex items-center justify-between gap-2">
        <h2 className="min-w-0 flex-1 truncate font-display text-sm font-semibold text-[var(--text-primary)]">
          {displayMission ? displayMission.title : "Mission"}
        </h2>
        <div className="flex shrink-0 items-center gap-1">
          <LiveLinkIndicator phase={streamPhase} />
          <button
            type="button"
            className="rounded-lg p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
            aria-label="Search"
          >
            <Search className="h-4 w-4" />
          </button>
          <button
            type="button"
            className="rounded-lg p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
            aria-label="Options"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
          {onClose ? (
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] lg:hidden"
              aria-label="Close panel"
            >
              ×
            </button>
          ) : null}
        </div>
        </div>
        {streamPhase !== "live" ? (
          <p className="text-[10px] leading-snug text-[var(--text-muted)]" role="status">
            {streamPhase === "reconnecting" ? operatorCopy.liveReconnecting : operatorCopy.liveOfflinePolling}
          </p>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {missionsLoading && missions.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">Loading…</p>
        ) : !displayMission ? (
          <p className="text-sm text-[var(--text-secondary)]">No active missions</p>
        ) : (
          <>
            {panelLoading ? (
              <p className="mb-4 text-xs text-[var(--text-muted)]">Syncing mission…</p>
            ) : null}

            <section className="mb-5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h3 className="min-w-0 flex-1 font-display text-base font-semibold leading-snug text-[var(--text-primary)]">
                  {displayMission.title}
                </h3>
                <StatusBadge status={normalizeMissionStatus(displayMission.status)} />
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] text-[var(--text-muted)]">
                {displayMission.current_stage?.trim() ? (
                  <span className="truncate">
                    Stage <span className="text-[var(--text-secondary)]">{displayMission.current_stage}</span>
                  </span>
                ) : (
                  <span className="text-[var(--text-muted)]/80">Stage —</span>
                )}
                <span aria-hidden className="text-[var(--bg-border)]">
                  ·
                </span>
                <span>Updated {formatRelativeTime(displayMission.updated_at)}</span>
                {pendingForMission.length > 0 ? (
                  <>
                    <span aria-hidden className="text-[var(--bg-border)]">
                      ·
                    </span>
                    <span className="font-semibold text-[var(--status-amber)]">Approval open</span>
                  </>
                ) : null}
              </div>
              <p className="mt-1 font-mono text-[10px] text-[var(--text-muted)]">
                Created {formatRelativeTime(displayMission.created_at)}
              </p>
            </section>

            {latestExecution?.hasResult ? (
              <section className="mb-4" aria-label="Latest execution output">
                <LatestExecutionResultLine
                  latest={latestExecution}
                  to={missionDetailLatestResultHref(displayMission.id, latestExecution)}
                  onNavigate={() => setThreadMissionId(displayMission.id)}
                />
              </section>
            ) : null}
            {executiveSummary ? (
              <section className="mb-6">
                <MissionExecutiveSummaryBlock summary={executiveSummary} variant="panel" />
              </section>
            ) : null}

            <section className="mb-6">
              <div className="mb-3 flex items-center gap-2">
                <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                  Approvals
                </h3>
                <span className="rounded-full bg-[var(--status-amber)]/20 px-2 py-0.5 text-[10px] font-bold text-[var(--status-amber)]">
                  {approvalsLoading && pendingForMission.length === 0 ? "…" : pendingForMission.length}
                </span>
              </div>
              {pendingForMission.length === 0 ? (
                <p className="text-xs text-[var(--text-secondary)]">
                  {displayMission.status === "awaiting_approval"
                    ? "Approval pending — check inbox or timeline."
                    : "No pending approvals"}
                </p>
              ) : (
                <div className="flex flex-col gap-3">
                  {pendingForMission.map((a) => (
                    <ApprovalCard
                      key={a.id}
                      approval={a}
                      resolving={resolvingApprovalId === a.id}
                      resolveError={resolveErrorApprovalId === a.id ? "err" : null}
                      recentlyResolvedDecision={recentlyResolvedDecisionFor(a.id)}
                      onApprove={() => void resolve(a.id, "approved")}
                      onDeny={() => void resolve(a.id, "denied")}
                    />
                  ))}
                </div>
              )}
            </section>

            <section>
              <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Recent activity
              </h3>
              {activityEvents.length === 0 ? (
                <p className="text-xs text-[var(--text-secondary)]">Awaiting first execution update</p>
              ) : (
                <ul className="space-y-3 text-xs text-[var(--text-secondary)]">
                  {activityEvents.map((ev) => (
                    <li key={ev.id} className="flex gap-2">
                      <span className="text-[var(--text-muted)]">•</span>
                      <span>
                        {ev.event_type}{" "}
                        <span className="font-mono text-[10px] text-[var(--text-muted)]">
                          {formatRelativeTime(ev.created_at)}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
    </aside>
  );
}
