import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ConversationThread } from "../components/conversation/ConversationThread";
import { StatusBadge } from "../components/common/StatusBadge";
import { useShellOutlet } from "../components/layout/AppShell";
import { useControlPlaneLive, useMissions } from "../hooks/useControlPlane";
import { formatRelativeTime, normalizeMissionStatus } from "../lib/format";
import { deriveExecutiveMissionSummary } from "../lib/missionExecutiveSummary";
import { ExecutiveMissionCardLine } from "../components/mission/MissionExecutiveSummaryBlock";

export function Overview() {
  const ctx = useShellOutlet();
  const navigate = useNavigate();
  const live = useControlPlaneLive();
  const { missions, loading } = useMissions({ limit: 5 });

  const recent = useMemo(() => {
    return [...missions]
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
      .slice(0, 5);
  }, [missions]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 flex flex-col">
        <ConversationThread onVoiceClick={ctx.openVoiceMode} />
      </div>
      <div className="shrink-0 border-t border-[var(--bg-border)] px-3 py-3 md:px-6">
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Recent Missions
        </p>
        {loading && recent.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">Loading missions…</p>
        ) : recent.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">No missions yet</p>
        ) : (
          <ul className="space-y-3">
            {recent.map((m) => {
              const events = live.eventsByMissionId[m.id] ?? [];
              const exec = deriveExecutiveMissionSummary(m, events, live.pendingApprovals, null);
              return (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => navigate(`/missions/${encodeURIComponent(m.id)}`)}
                    className="flex w-full flex-col gap-0.5 rounded-lg px-1 py-1 text-left transition-colors hover:bg-[var(--bg-elevated)]/40"
                  >
                    <div className="flex w-full items-center gap-2">
                      <StatusBadge status={normalizeMissionStatus(m.status)} />
                      <span className="min-w-0 flex-1 truncate text-sm font-medium text-[var(--text-primary)]">
                        {m.title}
                      </span>
                      <span className="shrink-0 font-mono text-[10px] text-[var(--text-muted)]">
                        {formatRelativeTime(m.updated_at)}
                      </span>
                    </div>
                    <ExecutiveMissionCardLine
                      summary={exec}
                      className="mt-0.5 text-[10px] text-[var(--text-muted)]"
                    />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
