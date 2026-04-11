import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import * as api from "../lib/api";
import { ApprovalCard } from "../components/approvals/ApprovalCard";
import { MissionTimeline } from "../components/mission/MissionTimeline";
import { StatusBadge } from "../components/common/StatusBadge";
import { useShellOutlet } from "../components/layout/AppShell";
import { useControlPlaneLive, useResolveApprovalAction } from "../hooks/useControlPlane";
import type { Approval, Receipt } from "../lib/types";
import { formatRelativeTime, normalizeMissionStatus } from "../lib/format";
import { deriveExecutiveMissionSummary } from "../lib/missionExecutiveSummary";
import {
  deriveLatestExecutionResult,
  MISSION_DETAIL_RECEIPTS_SECTION_ID,
  missionDetailLatestResultHash,
} from "../lib/missionLatestResult";
import { MissionExecutiveSummaryBlock } from "../components/mission/MissionExecutiveSummaryBlock";
import { LatestExecutionResultLine } from "../components/mission/LatestExecutionResultLine";
import { MissionReceiptsSection } from "../components/mission/MissionReceiptsSection";
import { LiveLinkIndicator } from "../components/layout/LiveLinkIndicator";
import { operatorCopy } from "../lib/operatorCopy";
import { deriveMissionTiming } from "../lib/missionTiming";
import { MissionOperationalHealthRow, MissionTimingStrip } from "../components/mission/MissionObservability";
import { GovernedActionLauncher } from "../components/governed/GovernedActionLauncher";

export function MissionDetail() {
  const { missionId = "" } = useParams<{ missionId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const { setThreadMissionId } = useShellOutlet();
  const {
    eventStreamRevision,
    hydrateMissionBundle,
    missionById,
    eventsByMissionId,
    streamPhase,
    pendingError,
  } = useControlPlaneLive();
  const { resolve, resolvingApprovalId, resolveErrorApprovalId, recentlyResolvedDecisionFor } =
    useResolveApprovalAction();

  const mission = missionId ? missionById[missionId] ?? null : null;
  const events = missionId ? eventsByMissionId[missionId] ?? [] : [];

  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [bundleError, setBundleError] = useState<string | null>(null);
  const [initialDone, setInitialDone] = useState(false);
  useEffect(() => {
    if (!missionId.trim()) return;
    setThreadMissionId(missionId);
  }, [missionId, setThreadMissionId]);

  const loadBundle = useCallback(async () => {
    if (!missionId.trim()) return;
    try {
      const b = await api.getMissionBundle(missionId);
      hydrateMissionBundle(b);
      setApprovals(b.approvals);
      setReceipts(b.receipts);
      setBundleError(null);
    } catch (e: unknown) {
      setBundleError(e instanceof Error ? e.message : String(e));
    } finally {
      setInitialDone(true);
    }
  }, [missionId, hydrateMissionBundle]);

  useEffect(() => {
    setInitialDone(false);
    void loadBundle();
  }, [loadBundle, missionId]);

  useEffect(() => {
    if (!missionId.trim() || !initialDone) return;
    const t = window.setTimeout(() => {
      void Promise.all([api.getMissionApprovals(missionId), api.getMissionReceipts(missionId)]).then(([a, r]) => {
        setApprovals(a);
        setReceipts(r);
      });
    }, 400);
    return () => clearTimeout(t);
  }, [eventStreamRevision, missionId, initialDone]);

  const resolveOne = useCallback(
    (id: string, decision: "approved" | "denied") => {
      void resolve(id, decision, { onSuccess: () => loadBundle() });
    },
    [resolve, loadBundle]
  );

  const executiveSummary = useMemo(() => {
    if (!mission) return null;
    return deriveExecutiveMissionSummary(mission, events, approvals, receipts);
  }, [mission, events, approvals, receipts]);

  const latestExecution = useMemo(() => {
    if (!mission) return null;
    return deriveLatestExecutionResult(mission, events, receipts);
  }, [mission, events, receipts]);

  const missionTiming = useMemo(() => {
    if (!mission) return null;
    return deriveMissionTiming(events, mission);
  }, [mission, events]);

  const pendingCount = useMemo(
    () => approvals.filter((a) => a.status === "pending").length,
    [approvals]
  );

  const diagnosticsMsg = useMemo(() => {
    if (bundleError && mission) return operatorCopy.bundlePartial;
    if (streamPhase === "reconnecting") return operatorCopy.liveReconnecting;
    if (streamPhase === "offline") return operatorCopy.liveOfflinePolling;
    return null;
  }, [bundleError, mission, streamPhase]);

  const governanceStale =
    Boolean(mission) &&
    initialDone &&
    mission!.status === "awaiting_approval" &&
    pendingCount === 0 &&
    approvals.length > 0;

  useEffect(() => {
    const raw = location.hash.slice(1);
    if (!raw || !missionId.trim()) return;
    const el = document.getElementById(raw);
    if (!el) return;
    const details = el.querySelector("details");
    if (details && !details.open) details.open = true;
    requestAnimationFrame(() => {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [location.hash, missionId, receipts.length, initialDone, mission?.id]);

  if (!missionId.trim()) {
    return <Navigate to="/missions" replace />;
  }

  if (initialDone && bundleError && !mission) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
        <p className="text-sm text-[var(--text-secondary)]">Mission not found or unavailable.</p>
        <Link
          to="/missions"
          className="text-sm font-medium text-[var(--accent-blue)] hover:underline"
        >
          Back to missions
        </Link>
      </div>
    );
  }

  const loadingShell = !initialDone && !mission;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <header className="shrink-0 border-b border-[var(--bg-border)] px-4 py-4 md:px-6">
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="inline-flex w-fit items-center gap-2 text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
              Back
            </button>
            <LiveLinkIndicator phase={streamPhase} alwaysVisible />
          </div>

          {diagnosticsMsg ? (
            <p className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)]/60 px-3 py-2 text-[11px] leading-snug text-[var(--text-secondary)]">
              {diagnosticsMsg}
            </p>
          ) : null}
          {governanceStale ? (
            <p className="text-[11px] text-[var(--status-amber)]">Approval pending — refreshing approvals.</p>
          ) : null}

          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <h1 className="font-display text-lg font-semibold leading-snug text-[var(--text-primary)] md:text-xl">
                {mission?.title ?? (loadingShell ? "Loading…" : "Mission")}
              </h1>
              {mission ? (
                <p className="mt-1 font-mono text-[10px] text-[var(--text-muted)]">{mission.id}</p>
              ) : null}
              {mission && executiveSummary ? (
                <p
                  className="mt-2 text-sm leading-snug text-[var(--text-secondary)]"
                  role="status"
                  aria-live="polite"
                >
                  {executiveSummary.phaseLabel}
                </p>
              ) : null}
              {latestExecution?.hasResult ? (
                <LatestExecutionResultLine
                  latest={latestExecution}
                  className="mt-3"
                  to={missionDetailLatestResultHash(latestExecution)}
                />
              ) : null}
            </div>
            {mission ? (
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={normalizeMissionStatus(mission.status)} />
                {pendingCount > 0 ? (
                  <span
                    className="rounded-full border border-[var(--status-amber)]/35 bg-[var(--status-amber)]/12 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-[var(--status-amber)]"
                    title="Pending approval"
                  >
                    Approval
                  </span>
                ) : null}
              </div>
            ) : null}
          </div>

          {mission ? (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[10px] text-[var(--text-muted)]">
              {mission.current_stage?.trim() ? (
                <span>
                  Stage <span className="text-[var(--text-secondary)]">{mission.current_stage}</span>
                </span>
              ) : (
                <span className="text-[var(--text-muted)]/80">Stage —</span>
              )}
              <span aria-hidden className="text-[var(--bg-border)]">
                ·
              </span>
              <span title="Last mission update">
                Updated {formatRelativeTime(mission.updated_at)}
              </span>
            </div>
          ) : null}

          {executiveSummary && mission ? (
            <MissionExecutiveSummaryBlock summary={executiveSummary} variant="detail" />
          ) : null}
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 md:px-6">
        <div className="mx-auto flex max-w-3xl flex-col gap-10">
          {mission && missionTiming ? (
            <div className="space-y-2">
              <MissionTimingStrip timing={missionTiming} mission={mission} />
              <MissionOperationalHealthRow
                streamPhase={streamPhase}
                pendingError={pendingError}
                bundleError={bundleError}
                mission={mission}
                hasReceipt={receipts.length > 0}
              />
            </div>
          ) : null}

          <section>
            <h2 className="mb-4 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Timeline
            </h2>
            {loadingShell && events.length === 0 ? (
              <p className="text-xs text-[var(--text-muted)]">Loading events…</p>
            ) : (
              <MissionTimeline
                events={events}
                missionStatus={mission?.status}
                phaseLabel={executiveSummary?.phaseLabel ?? null}
              />
            )}
          </section>

          {mission ? <GovernedActionLauncher missionId={mission.id} /> : null}

          <section>
            <h2 className="mb-4 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Approvals
            </h2>
            {!initialDone && approvals.length === 0 ? (
              <p className="text-xs text-[var(--text-muted)]">Loading…</p>
            ) : approvals.length === 0 ? (
              <p className="text-xs text-[var(--text-secondary)]">
                {mission?.status === "awaiting_approval"
                  ? "Approval pending — no request object yet."
                  : "No approval records for this mission."}
              </p>
            ) : (
              <div className="flex flex-col gap-3">
                {approvals.map((a) => (
                  <ApprovalCard
                    key={a.id}
                    approval={a}
                    muted={a.status !== "pending"}
                    resolving={resolvingApprovalId === a.id}
                    resolveError={resolveErrorApprovalId === a.id ? "err" : null}
                    recentlyResolvedDecision={
                      a.status === "pending" ? recentlyResolvedDecisionFor(a.id) : null
                    }
                    onApprove={
                      a.status === "pending" ? () => void resolveOne(a.id, "approved") : undefined
                    }
                    onDeny={a.status === "pending" ? () => void resolveOne(a.id, "denied") : undefined}
                  />
                ))}
              </div>
            )}
          </section>

          <section id={MISSION_DETAIL_RECEIPTS_SECTION_ID} className="scroll-mt-24">
            <h2 className="mb-4 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Receipts
            </h2>
            <MissionReceiptsSection
              mission={mission}
              receipts={receipts}
              loading={!initialDone && receipts.length === 0}
              latestExecution={latestExecution}
            />
          </section>
        </div>
      </div>
    </div>
  );
}
