import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ConversationThread } from "../components/conversation/ConversationThread";
import { StatusBadge } from "../components/common/StatusBadge";
import { useShellOutlet } from "../components/layout/AppShell";
import { useMissions } from "../hooks/useControlPlane";
import { formatRelativeTime } from "../lib/format";

type MissionStatus = "pending" | "active" | "blocked" | "awaiting_approval" | "complete" | "failed";

function toMissionStatus(s: string): MissionStatus {
  const allowed: MissionStatus[] = [
    "pending",
    "active",
    "blocked",
    "awaiting_approval",
    "complete",
    "failed",
  ];
  return (allowed.includes(s as MissionStatus) ? s : "pending") as MissionStatus;
}

export function Overview() {
  const ctx = useShellOutlet();
  const navigate = useNavigate();
  const { missions } = useMissions({ limit: 3 });

  const recent = useMemo(() => {
    return [...missions]
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
      .slice(0, 3);
  }, [missions]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 flex flex-col">
        <ConversationThread onVoiceClick={ctx.openVoiceMode} />
      </div>
      {recent.length > 0 ? (
        <div className="shrink-0 border-t border-[var(--bg-border)] px-3 py-3 md:px-6">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Recent Missions
          </p>
          <ul className="space-y-2">
            {recent.map((m) => (
              <li key={m.id}>
                <button
                  type="button"
                  onClick={() => navigate("/missions")}
                  className="flex w-full items-center gap-2 text-left text-sm text-[var(--text-primary)]"
                >
                  <StatusBadge status={toMissionStatus(m.status)} />
                  <span className="min-w-0 flex-1 truncate">{m.title}</span>
                  <span className="shrink-0 font-mono text-[10px] text-[var(--text-muted)]">
                    {formatRelativeTime(m.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
