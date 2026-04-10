import { useCallback, useMemo, useState } from "react";
import { MoreHorizontal, Search } from "lucide-react";
import * as api from "../../lib/api";
import { usePendingApprovals, usePolledMissionDetail } from "../../hooks/useControlPlane";
import { ApprovalCard } from "../approvals/ApprovalCard";
import { StatusBadge } from "../common/StatusBadge";
import type { Approval, Mission } from "../../lib/types";
import { formatRelativeTime, normalizeMissionStatus, selectFocusMission } from "../../lib/format";

export function RightPanel({
  missions,
  missionsLoading,
  onClose,
}: {
  missions: Mission[];
  missionsLoading: boolean;
  onClose?: () => void;
}) {
  const focusFromList = useMemo(() => selectFocusMission(missions), [missions]);
  const { approvals, loading: approvalsLoading, refetch } = usePendingApprovals({
    pollIntervalMs: 5000,
  });
  const { mission, events, loading: detailLoading } = usePolledMissionDetail(
    focusFromList?.id ?? null,
    5000
  );

  const displayMission = mission ?? focusFromList;
  const pendingForMission = useMemo(() => {
    if (!displayMission) return [] as Approval[];
    return approvals.filter((a) => a.mission_id === displayMission.id && a.status === "pending");
  }, [approvals, displayMission]);

  const activityEvents = useMemo(() => {
    const last = events.slice(-5);
    return [...last].reverse();
  }, [events]);

  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [resolveErrorId, setResolveErrorId] = useState<string | null>(null);

  const resolve = useCallback(
    async (id: string, decision: "approved" | "denied") => {
      setResolvingId(id);
      setResolveErrorId(null);
      try {
        await api.resolveApproval(id, {
          decision,
          decided_by: "operator",
          decided_via: "command_center",
        });
        await refetch();
      } catch {
        setResolveErrorId(id);
      } finally {
        setResolvingId(null);
      }
    },
    [refetch]
  );

  const panelLoading = missionsLoading || (displayMission != null && detailLoading && events.length === 0);

  return (
    <aside
      className="flex h-full w-full flex-col border-l border-[var(--bg-border)] lg:w-[320px] lg:shrink-0"
      style={{ backgroundColor: "var(--bg-surface)" }}
    >
      <div className="flex items-center justify-between border-b border-[var(--bg-border)] px-4 py-3">
        <h2 className="min-w-0 flex-1 truncate font-display text-sm font-semibold text-[var(--text-primary)]">
          {displayMission ? displayMission.title : "Mission"}
        </h2>
        <div className="flex shrink-0 items-center gap-1">
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

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {missionsLoading && missions.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">Loading…</p>
        ) : !displayMission ? (
          <p className="text-sm text-[var(--text-secondary)]">No active missions</p>
        ) : (
          <>
            {panelLoading ? (
              <p className="mb-4 text-xs text-[var(--text-muted)]">Loading mission…</p>
            ) : null}

            <section className="mb-6">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h3 className="min-w-0 flex-1 font-display text-base font-semibold leading-snug text-[var(--text-primary)]">
                  {displayMission.title}
                </h3>
                <StatusBadge status={normalizeMissionStatus(displayMission.status)} />
              </div>
              <p className="mt-2 font-mono text-[10px] text-[var(--text-muted)]">
                Created {formatRelativeTime(displayMission.created_at)}
              </p>
            </section>

            {displayMission.current_stage?.trim() ? (
              <section className="mb-6">
                <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                  Stage
                </h3>
                <p className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)] px-3 py-2 text-sm text-[var(--text-secondary)]">
                  {displayMission.current_stage}
                </p>
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
                <p className="text-xs text-[var(--text-muted)]">No pending approvals</p>
              ) : (
                <div className="flex flex-col gap-3">
                  {pendingForMission.map((a) => (
                    <ApprovalCard
                      key={a.id}
                      approval={a}
                      resolving={resolvingId === a.id}
                      resolveError={resolveErrorId === a.id ? "err" : null}
                      onApprove={() => resolve(a.id, "approved")}
                      onDeny={() => resolve(a.id, "denied")}
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
                <p className="text-xs text-[var(--text-muted)]">No activity yet</p>
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
