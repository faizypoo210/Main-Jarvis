import { useId, useMemo } from "react";
import { Link } from "react-router-dom";
import { ConversationThread } from "../components/conversation/ConversationThread";
import { StatusBadge } from "../components/common/StatusBadge";
import { useShellOutlet } from "../components/layout/AppShell";
import { useControlPlaneLive, useMissions, useResolveApprovalAction } from "../hooks/useControlPlane";
import { useOperatorHeartbeat } from "../hooks/useOperatorHeartbeat";
import { formatRelativeTime, normalizeMissionStatus } from "../lib/format";
import { approvalPostDecisionLine } from "../lib/approvalPresentation";
import { operatorCopy } from "../lib/operatorCopy";
import { deriveExecutiveMissionSummary, getPendingApprovalsForMission } from "../lib/missionExecutiveSummary";
import {
  capSettledForOverview,
  deriveOverviewRowFreshnessCue,
  filterOverviewRecentlyUpdatedBucket,
  groupMissionsForOverview,
  OVERVIEW_TRIAGE_SEARCH_PARAM,
  overviewFreshnessCueLabel,
  type OverviewTriageUrlParam,
} from "../lib/missionListPriority";
import type { Approval, Mission, MissionEvent } from "../lib/types";
import { ExecutiveMissionCardLine } from "../components/mission/MissionExecutiveSummaryBlock";
import { LatestExecutionResultLine } from "../components/mission/LatestExecutionResultLine";
import { deriveLatestExecutionResult, missionDetailLatestResultHref } from "../lib/missionLatestResult";

const rowFocusRing =
  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-blue)]/40 focus-visible:ring-offset-0";

function triageViewAllHref(bucket: OverviewTriageUrlParam): string {
  const p = new URLSearchParams();
  p.set(OVERVIEW_TRIAGE_SEARCH_PARAM, bucket);
  return `/missions?${p.toString()}`;
}

function handoffToMission(missionId: string, setThreadMissionId: (id: string | null) => void) {
  setThreadMissionId(missionId);
}

type ResolveHandlers = {
  onResolve: (approvalId: string, decision: "approved" | "denied") => void;
  resolvingApprovalId: string | null;
  resolveErrorApprovalId: string | null;
  recentlyResolvedDecisionFor: (approvalId: string) => "approved" | "denied" | null;
};

function NeedsAttentionTriageRow({
  mission,
  events,
  approvals,
  setThreadMissionId,
  resolveHandlers,
}: {
  mission: Mission;
  events: MissionEvent[];
  approvals: Approval[];
  setThreadMissionId: (id: string | null) => void;
  resolveHandlers: ResolveHandlers;
}) {
  const exec = useMemo(
    () => deriveExecutiveMissionSummary(mission, events, approvals, null),
    [mission, events, approvals]
  );
  const cue = useMemo(
    () => deriveOverviewRowFreshnessCue(mission, events, approvals, null, "needs_attention"),
    [mission, events, approvals]
  );
  const cueLabel = cue != null ? overviewFreshnessCueLabel(cue) : null;
  const pending = useMemo(
    () => getPendingApprovalsForMission(mission.id, approvals),
    [mission.id, approvals]
  );
  const preview = useMemo(() => {
    if (pending.length === 1) {
      const a = pending[0]!;
      const raw = a.reason?.trim();
      const reason =
        raw && raw.length > 120 ? `${raw.slice(0, 120)}…` : raw && raw.length > 0 ? raw : null;
      return { kind: "single" as const, approval: a, reason };
    }
    if (pending.length > 1) {
      return { kind: "many" as const, count: pending.length };
    }
    return null;
  }, [pending]);

  const to = `/missions/${encodeURIComponent(mission.id)}`;
  const ariaPreview =
    preview?.kind === "single"
      ? ` — ${preview.approval.action_type}, risk ${preview.approval.risk_class}${preview.reason ? `, ${preview.reason}` : ""}`
      : preview?.kind === "many"
        ? ` — ${preview.count} pending approvals`
        : "";
  const ariaCue = cueLabel ? ` — ${cueLabel}` : "";
  const singlePending = pending.length === 1 ? pending[0]! : null;
  const showInlineResolve =
    singlePending != null &&
    singlePending.id.trim().length > 0 &&
    singlePending.action_type.trim().length > 0;

  const { onResolve, resolvingApprovalId, resolveErrorApprovalId, recentlyResolvedDecisionFor } =
    resolveHandlers;
  const resolving = resolvingApprovalId === singlePending?.id;
  const recentlyResolvedDecision =
    singlePending != null ? recentlyResolvedDecisionFor(singlePending.id) : null;
  const showRaceSuccess = Boolean(
    singlePending != null && recentlyResolvedDecision != null && !resolving
  );

  return (
    <li>
      <div className="flex gap-2 rounded-lg px-1 py-1 transition-colors hover:bg-[var(--bg-elevated)]/40">
        <Link
          to={to}
          onClick={() => handoffToMission(mission.id, setThreadMissionId)}
          className={`flex min-w-0 flex-1 flex-col gap-1 rounded-md px-0.5 py-0.5 text-left ${rowFocusRing}`}
          aria-label={`Open mission: ${mission.title}${ariaCue}${ariaPreview}`}
        >
          <div className="flex w-full items-center gap-2">
            <StatusBadge status={normalizeMissionStatus(mission.status)} />
            <span className="min-w-0 flex-1 truncate text-sm font-medium text-[var(--text-primary)]">
              {mission.title}
            </span>
            <div className="flex shrink-0 flex-col items-end gap-0.5 sm:flex-row sm:items-center sm:gap-2">
              {cueLabel ? (
                <span className="whitespace-nowrap text-[9px] font-medium leading-none text-[var(--text-secondary)]">
                  {cueLabel}
                </span>
              ) : null}
              <span className="whitespace-nowrap font-mono text-[10px] text-[var(--text-muted)]">
                {formatRelativeTime(mission.updated_at)}
              </span>
            </div>
          </div>
          {preview?.kind === "single" ? (
            <p className="line-clamp-2 text-[10px] leading-snug text-[var(--text-muted)]">
              <span className="text-[var(--text-secondary)]">{preview.approval.action_type}</span>
              <span aria-hidden> · </span>
              <span className="font-mono text-[9px] uppercase tracking-wide text-[var(--text-muted)]">
                {preview.approval.risk_class}
              </span>
              {preview.reason ? (
                <>
                  <span aria-hidden> · </span>
                  {preview.reason}
                </>
              ) : null}
            </p>
          ) : preview?.kind === "many" ? (
            <p className="text-[10px] text-[var(--text-muted)]">
              {preview.count} pending approvals — open the mission to review.
            </p>
          ) : exec.pendingApprovalLine ? (
            <p className="line-clamp-2 text-[10px] text-[var(--text-muted)]">{exec.pendingApprovalLine}</p>
          ) : null}
          <ExecutiveMissionCardLine
            summary={exec}
            className="mt-0.5 text-[10px] text-[var(--text-muted)]"
          />
        </Link>
        <div className="flex shrink-0 flex-col items-end gap-1.5 self-start pt-0.5">
          <Link
            to={to}
            onClick={() => handoffToMission(mission.id, setThreadMissionId)}
            className={`whitespace-nowrap text-[10px] font-medium text-[var(--text-secondary)] underline-offset-2 transition-colors hover:underline ${rowFocusRing} rounded px-0.5 py-0.5`}
            aria-label={`Review mission: ${mission.title}`}
          >
            Review
          </Link>
          {showInlineResolve ? (
            <div
              className="flex flex-col gap-1"
              role="group"
              aria-label={`Governance decision for ${mission.title}`}
              aria-busy={resolving || showRaceSuccess ? "true" : undefined}
            >
              {showRaceSuccess ? (
                <div className="max-w-[9rem] rounded border border-[var(--bg-border)] bg-[var(--bg-void)]/60 px-2 py-1.5 text-right">
                  <p className="text-[9px] font-medium leading-snug text-[var(--text-secondary)]" role="status">
                    {approvalPostDecisionLine(recentlyResolvedDecision!)}
                  </p>
                  <p className="mt-0.5 text-[8px] text-[var(--text-muted)]">
                    {operatorCopy.approvalRefreshingState}
                  </p>
                </div>
              ) : (
                <>
                  {resolving ? (
                    <p className="max-w-[7rem] text-right text-[9px] text-[var(--text-muted)]" role="status" aria-live="polite">
                      {operatorCopy.approvalRecording}
                    </p>
                  ) : null}
                  <button
                    type="button"
                    disabled={resolving}
                    aria-disabled={resolving}
                    onClick={() => onResolve(singlePending.id, "approved")}
                    className="rounded border border-[var(--bg-border)] bg-[var(--bg-void)]/60 px-2 py-1 text-[10px] font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)]/70 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    disabled={resolving}
                    aria-disabled={resolving}
                    onClick={() => onResolve(singlePending.id, "denied")}
                    className="rounded border border-[var(--bg-border)] bg-transparent px-2 py-1 text-[10px] font-medium text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-elevated)]/50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Deny
                  </button>
                  {resolveErrorApprovalId === singlePending.id ? (
                    <p className="max-w-[7rem] text-right text-[9px] text-[var(--text-muted)]">
                      {operatorCopy.approvalResolveFailed}
                    </p>
                  ) : null}
                </>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function OverviewTriageRow({
  mission,
  events,
  approvals,
  setThreadMissionId,
  bucket,
  showLatestExecutionResult,
}: {
  mission: Mission;
  events: MissionEvent[];
  approvals: Approval[];
  setThreadMissionId: (id: string | null) => void;
  bucket: OverviewTriageUrlParam | "settled";
  /** Extra compact execution-evidence line for the “Recently updated” bucket. */
  showLatestExecutionResult?: boolean;
}) {
  const exec = useMemo(
    () => deriveExecutiveMissionSummary(mission, events, approvals, null),
    [mission, events, approvals]
  );
  const latestExec = useMemo(
    () => deriveLatestExecutionResult(mission, events, null),
    [mission, events]
  );
  const cue = useMemo(
    () => deriveOverviewRowFreshnessCue(mission, events, approvals, null, bucket),
    [mission, events, approvals, bucket]
  );
  const cueLabel = cue != null ? overviewFreshnessCueLabel(cue) : null;
  const ariaCue = cueLabel ? ` — ${cueLabel}` : "";
  const to = `/missions/${encodeURIComponent(mission.id)}`;
  return (
    <li>
      <div className="flex w-full flex-col gap-0.5 rounded-lg px-1 py-1">
        <Link
          to={to}
          onClick={() => handoffToMission(mission.id, setThreadMissionId)}
          className={`flex w-full flex-col gap-0.5 text-left transition-colors hover:bg-[var(--bg-elevated)]/40 ${rowFocusRing} rounded-md px-0.5 py-0.5`}
          aria-label={`Open mission: ${mission.title}${ariaCue}`}
        >
          <div className="flex w-full items-center gap-2">
            <StatusBadge status={normalizeMissionStatus(mission.status)} />
            <span className="min-w-0 flex-1 truncate text-sm font-medium text-[var(--text-primary)]">
              {mission.title}
            </span>
            <div className="flex shrink-0 flex-col items-end gap-0.5 sm:flex-row sm:items-center sm:gap-2">
              {cueLabel ? (
                <span className="whitespace-nowrap text-[9px] font-medium leading-none text-[var(--text-secondary)]">
                  {cueLabel}
                </span>
              ) : null}
              <span className="whitespace-nowrap font-mono text-[10px] text-[var(--text-muted)]">
                {formatRelativeTime(mission.updated_at)}
              </span>
            </div>
          </div>
          <ExecutiveMissionCardLine
            summary={exec}
            className="mt-0.5 text-[10px] text-[var(--text-muted)]"
          />
        </Link>
        {showLatestExecutionResult && latestExec.hasResult ? (
          <LatestExecutionResultLine
            latest={latestExec}
            dense
            className="mt-1 border-t border-[var(--bg-border)]/60 px-0.5 pt-1"
            to={missionDetailLatestResultHref(mission.id, latestExec)}
            onNavigate={() => handoffToMission(mission.id, setThreadMissionId)}
          />
        ) : null}
      </div>
    </li>
  );
}

function TriageSection({
  title,
  count,
  emptyLabel,
  missions,
  eventsByMissionId,
  approvals,
  setThreadMissionId,
  viewAllBucket,
  resolveHandlers,
}: {
  title: string;
  count: number;
  emptyLabel: string;
  missions: Mission[];
  eventsByMissionId: Record<string, MissionEvent[]>;
  approvals: Approval[];
  setThreadMissionId: (id: string | null) => void;
  viewAllBucket: OverviewTriageUrlParam;
  resolveHandlers?: ResolveHandlers;
}) {
  const headingId = useId();
  const viewAllTo = triageViewAllHref(viewAllBucket);
  const showLatestExecutionResult = viewAllBucket === "recently_updated";

  const freshCount = useMemo(() => {
    if (missions.length === 0) return 0;
    return missions.filter((m) => {
      const ev = eventsByMissionId[m.id] ?? [];
      return deriveOverviewRowFreshnessCue(m, ev, approvals, null, viewAllBucket) !== null;
    }).length;
  }, [missions, eventsByMissionId, approvals, viewAllBucket]);

  const needsAttention = viewAllBucket === "needs_attention" && resolveHandlers != null;

  return (
    <section className="space-y-2" aria-labelledby={headingId}>
      <div className="flex items-baseline justify-between gap-2">
        <h3
          id={headingId}
          className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]"
        >
          {title}{" "}
          <span className="text-[var(--text-muted)]">({count})</span>
          {freshCount > 0 ? (
            <span className="ml-1 font-normal normal-case text-[var(--text-muted)]"> · {freshCount} new</span>
          ) : null}
        </h3>
        <Link
          to={viewAllTo}
          aria-label={`View all missions: ${title}`}
          className={`shrink-0 text-[10px] font-medium text-[var(--text-muted)] transition-colors hover:text-[var(--text-secondary)] ${rowFocusRing} rounded px-0.5 py-0.5`}
        >
          View all
        </Link>
      </div>
      {count === 0 ? (
        <p className="text-xs text-[var(--text-muted)]">{emptyLabel}</p>
      ) : (
        <ul className="space-y-3">
          {missions.map((m) =>
            needsAttention ? (
              <NeedsAttentionTriageRow
                key={m.id}
                mission={m}
                events={eventsByMissionId[m.id] ?? []}
                approvals={approvals}
                setThreadMissionId={setThreadMissionId}
                resolveHandlers={resolveHandlers}
              />
            ) : (
              <OverviewTriageRow
                key={m.id}
                mission={m}
                events={eventsByMissionId[m.id] ?? []}
                approvals={approvals}
                setThreadMissionId={setThreadMissionId}
                bucket={viewAllBucket}
                showLatestExecutionResult={showLatestExecutionResult}
              />
            )
          )}
        </ul>
      )}
    </section>
  );
}

export function Overview() {
  const ctx = useShellOutlet();
  const live = useControlPlaneLive();
  const heartbeat = useOperatorHeartbeat(90000);
  const { missions, loading } = useMissions();
  const { resolve, resolvingApprovalId, resolveErrorApprovalId, recentlyResolvedDecisionFor } =
    useResolveApprovalAction();

  const resolveHandlers: ResolveHandlers = useMemo(
    () => ({
      onResolve: (approvalId, decision) => void resolve(approvalId, decision),
      resolvingApprovalId,
      resolveErrorApprovalId,
      recentlyResolvedDecisionFor,
    }),
    [resolve, resolvingApprovalId, resolveErrorApprovalId, recentlyResolvedDecisionFor]
  );

  const grouped = useMemo(() => {
    const g = groupMissionsForOverview(
      missions,
      live.eventsByMissionId,
      live.pendingApprovals,
      null
    );
    return {
      ...g,
      recently_updated: filterOverviewRecentlyUpdatedBucket(
        g.recently_updated,
        live.eventsByMissionId,
        live.pendingApprovals,
        null
      ),
    };
  }, [missions, live.eventsByMissionId, live.pendingApprovals]);

  const settledDisplay = useMemo(
    () => capSettledForOverview(grouped.settled),
    [grouped.settled]
  );

  const settledHeadingId = useId();

  const shared = {
    eventsByMissionId: live.eventsByMissionId,
    approvals: live.pendingApprovals,
    setThreadMissionId: ctx.setThreadMissionId,
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-0 flex-1 flex-col">
        <ConversationThread onVoiceClick={ctx.openVoiceMode} />
      </div>
      <div className="shrink-0 border-t border-[var(--bg-border)] px-3 py-3 md:px-6">
        {heartbeat.data && heartbeat.data.open_count > 0 ? (
          <div
            className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--status-amber)]/35 bg-[var(--status-amber)]/10 px-3 py-2 text-[11px] text-[var(--text-secondary)]"
            role="status"
          >
            <span>
              Heartbeat supervision:{" "}
              <span className="font-mono font-semibold text-[var(--text-primary)]">
                {heartbeat.data.open_count}
              </span>{" "}
              open {heartbeat.data.open_count === 1 ? "finding" : "findings"} (deduped).
            </span>
            <Link
              to="/activity"
              className="shrink-0 font-medium text-[var(--accent-blue)] underline-offset-2 hover:underline"
            >
              View in Activity
            </Link>
          </div>
        ) : null}
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Mission triage
        </p>
        {loading && missions.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">Loading missions…</p>
        ) : missions.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">No missions yet</p>
        ) : (
          <div className="max-h-[min(52vh,28rem)] space-y-5 overflow-y-auto pr-1">
            <TriageSection
              title="Needs attention"
              count={grouped.needs_attention.length}
              emptyLabel="No approvals or stalled runs."
              missions={grouped.needs_attention}
              viewAllBucket="needs_attention"
              resolveHandlers={resolveHandlers}
              {...shared}
            />
            <TriageSection
              title="Running"
              count={grouped.running.length}
              emptyLabel="No active execution right now."
              missions={grouped.running}
              viewAllBucket="running"
              {...shared}
            />
            <TriageSection
              title="Recently updated"
              count={grouped.recently_updated.length}
              emptyLabel="No fresh execution updates."
              missions={grouped.recently_updated}
              viewAllBucket="recently_updated"
              {...shared}
            />
            {grouped.settled.length > 0 ? (
              <section className="space-y-2 border-t border-[var(--bg-border)]/80 pt-4" aria-labelledby={settledHeadingId}>
                <h3
                  id={settledHeadingId}
                  className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]"
                >
                  Settled ({grouped.settled.length})
                </h3>
                {grouped.settled.length > settledDisplay.length ? (
                  <p className="text-[10px] text-[var(--text-muted)]">
                    Showing {settledDisplay.length} most recent.
                  </p>
                ) : null}
                <ul className="space-y-3">
                  {settledDisplay.map((m) => (
                    <OverviewTriageRow
                      key={m.id}
                      mission={m}
                      events={shared.eventsByMissionId[m.id] ?? []}
                      approvals={shared.approvals}
                      setThreadMissionId={shared.setThreadMissionId}
                      bucket="settled"
                    />
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
