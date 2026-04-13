import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ListTodo } from "lucide-react";
import { MissionList } from "../components/missions/MissionList";
import { useControlPlaneLive, useMissions } from "../hooks/useControlPlane";
import {
  getMissionOverviewTriageBucket,
  OVERVIEW_TRIAGE_SEARCH_PARAM,
  overviewTriageHandoffLabels,
  parseOverviewTriageSearchParam,
  sortMissionsForOperatorListing,
} from "../lib/missionListPriority";

const tabs = ["All", "Active", "Awaiting Approval", "Complete", "Failed"] as const;

function tabToStatus(tab: (typeof tabs)[number]): string | undefined {
  if (tab === "All") return undefined;
  if (tab === "Active") return "active";
  if (tab === "Awaiting Approval") return "awaiting_approval";
  if (tab === "Complete") return "complete";
  if (tab === "Failed") return "failed";
  return undefined;
}

function MissionCardSkeleton() {
  return (
    <div
      className="animate-pulse rounded-xl border border-[var(--bg-border)] p-4"
      style={{ backgroundColor: "var(--bg-surface)" }}
    >
      <div className="h-4 w-2/3 rounded bg-[var(--bg-border)] opacity-60" />
      <div className="mt-3 h-3 w-full rounded bg-[var(--bg-border)] opacity-40" />
      <div className="mt-2 h-3 w-4/5 rounded bg-[var(--bg-border)] opacity-40" />
      <div className="mt-3 flex gap-3">
        <div className="h-2 w-20 rounded bg-[var(--bg-border)] opacity-50" />
        <div className="h-2 w-24 rounded bg-[var(--bg-border)] opacity-50" />
      </div>
    </div>
  );
}

export function Missions() {
  const [tab, setTab] = useState<(typeof tabs)[number]>("All");
  const [searchParams, setSearchParams] = useSearchParams();
  const live = useControlPlaneLive();
  const { missions: raw, loading, error } = useMissions({ limit: 500 });

  const triageParam = useMemo(
    () => parseOverviewTriageSearchParam(searchParams.get(OVERVIEW_TRIAGE_SEARCH_PARAM)),
    [searchParams]
  );

  useEffect(() => {
    if (triageParam) setTab("All");
  }, [triageParam]);

  const clearTriageHandoff = useCallback(() => {
    setSearchParams({}, { replace: true });
  }, [setSearchParams]);

  const selectTab = useCallback(
    (t: (typeof tabs)[number]) => {
      setTab(t);
      if (searchParams.get(OVERVIEW_TRIAGE_SEARCH_PARAM)) {
        setSearchParams({}, { replace: true });
      }
    },
    [searchParams, setSearchParams]
  );

  const filtered = useMemo(() => {
    if (triageParam) {
      const matches = raw.filter((m) => {
        const ev = live.eventsByMissionId[m.id] ?? [];
        return getMissionOverviewTriageBucket(m, ev, live.pendingApprovals, null) === triageParam;
      });
      return sortMissionsForOperatorListing(
        matches,
        live.eventsByMissionId,
        live.pendingApprovals,
        null
      );
    }
    const want = tabToStatus(tab);
    if (!want) return raw;
    return raw.filter((m) => m.status === want);
  }, [raw, tab, triageParam, live.eventsByMissionId, live.pendingApprovals]);

  const handoffLabel = triageParam != null ? overviewTriageHandoffLabels[triageParam] : null;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      {error ? (
        <div className="shrink-0 border-b border-[var(--status-amber)]/30 bg-[var(--status-amber)]/10 px-4 py-2 text-center text-xs text-[var(--status-amber)] md:px-6">
          Could not reach control plane
        </div>
      ) : null}
      <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-[var(--bg-border)] px-4 py-3 md:px-6">
        <span className="font-mono text-xs text-[var(--text-muted)]">{filtered.length} total</span>
      </div>
      {triageParam && handoffLabel ? (
        <div
          className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[var(--bg-border)] px-4 py-2 md:px-6"
          role="status"
        >
          <p className="text-xs text-[var(--text-muted)]">
            Overview handoff: <span className="text-[var(--text-secondary)]">{handoffLabel}</span>
          </p>
          <button
            type="button"
            onClick={clearTriageHandoff}
            className="text-xs font-medium text-[var(--text-muted)] underline decoration-[var(--bg-border)] underline-offset-2 transition-colors hover:text-[var(--text-secondary)] focus-visible:rounded focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-blue)]/40"
          >
            Clear filter
          </button>
        </div>
      ) : null}
      <div className="flex gap-2 overflow-x-auto border-b border-[var(--bg-border)] px-4 py-2 md:px-6">
        {tabs.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => selectTab(t)}
            className={`whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium transition-colors duration-150 ease-linear ${
              tab === t
                ? "bg-[var(--accent-blue-glow)] text-[var(--accent-blue)]"
                : "text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-secondary)]"
            }`}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-6">
        {loading && raw.length === 0 ? (
          <div className="flex flex-col gap-3">
            <MissionCardSkeleton />
            <MissionCardSkeleton />
            <MissionCardSkeleton />
          </div>
        ) : !loading && filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
            <ListTodo className="h-10 w-10 text-[var(--text-muted)] opacity-50" aria-hidden />
            <p className="text-sm text-[var(--text-muted)]">
              {triageParam ? "No missions in this overview view." : "No missions yet"}
            </p>
            {triageParam ? (
              <Link
                to="/missions"
                replace
                className="text-xs font-medium text-[var(--text-muted)] underline-offset-2 hover:text-[var(--text-secondary)] focus-visible:rounded focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-blue)]/40"
              >
                Show all missions
              </Link>
            ) : (
              <>
                <p className="max-w-sm text-xs text-[var(--text-muted)]">
                  Send a command from Overview to create a mission — there is no separate &quot;new mission&quot; form here.
                </p>
                <Link
                  to="/"
                  className="text-xs font-medium text-[var(--accent-blue)] underline-offset-2 hover:opacity-90 focus-visible:rounded focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-blue)]/40"
                >
                  Go to Overview
                </Link>
              </>
            )}
          </div>
        ) : (
          <MissionList missions={filtered} />
        )}
      </div>
    </div>
  );
}
