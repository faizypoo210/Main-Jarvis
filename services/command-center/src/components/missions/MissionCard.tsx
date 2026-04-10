import { RiskBadge, type Risk } from "../common/RiskBadge";
import { StatusBadge } from "../common/StatusBadge";
import type { Mission } from "../../lib/types";
import { formatCreatedByLabel, formatRelativeTime, normalizeMissionStatus } from "../../lib/format";

function toRisk(r: string | null): Risk | null {
  if (r === "green" || r === "amber" || r === "red") return r;
  return null;
}

export function MissionCard({ mission }: { mission: Mission }) {
  const desc = mission.description?.trim() || mission.summary?.trim() || "";
  const risk = toRisk(mission.risk_class);

  return (
    <article
      className="rounded-xl border border-[var(--bg-border)] p-4 transition-colors duration-150 ease-linear hover:bg-[var(--bg-elevated)]/50"
      style={{ backgroundColor: "var(--bg-surface)" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="font-display text-base font-semibold text-[var(--text-primary)]">{mission.title}</h3>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={normalizeMissionStatus(mission.status)} />
          {risk ? <RiskBadge risk={risk} /> : null}
        </div>
      </div>
      {desc ? (
        <p className="mt-2 line-clamp-2 text-sm text-[var(--text-secondary)]">{desc}</p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-3 font-mono text-[10px] text-[var(--text-muted)]">
        <span>{formatCreatedByLabel(mission.created_by)}</span>
        <span>{formatRelativeTime(mission.created_at)}</span>
      </div>
    </article>
  );
}
