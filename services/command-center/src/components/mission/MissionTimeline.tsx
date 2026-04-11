import type { MissionEvent } from "../../lib/types";
import { formatRelativeTime } from "../../lib/format";
import { ExecutionMetaLine } from "./ExecutionMetaLine";
import { operatorCopy } from "../../lib/operatorCopy";

function timelineEventTitle(ev: MissionEvent): string {
  const p = ev.payload as Record<string, unknown> | null;
  if (ev.event_type === "routing_decided" && p) {
    const req = typeof p.requested_lane === "string" ? p.requested_lane : "";
    const act = typeof p.actual_lane === "string" ? p.actual_lane : "";
    const fb = p.fallback_applied === true;
    if (fb && req === "local_fast" && act === "gateway") {
      return "Routing decided: local-fast, fell back to gateway";
    }
    if (act === "gateway") return "Routing decided: gateway";
    if (act === "local_fast") return "Routing decided: local-fast";
  }
  switch (ev.event_type) {
    case "created":
      return "Mission created";
    case "mission_status_changed":
      return "Status changed";
    case "approval_requested":
      return "Approval requested";
    case "approval_resolved":
      return "Approval resolved";
    case "receipt_recorded":
      return "Receipt recorded";
    default:
      return ev.event_type.replace(/_/g, " ");
  }
}

function sortEventsChronological(events: MissionEvent[]): MissionEvent[] {
  return [...events].sort((a, b) => {
    const t = a.created_at.localeCompare(b.created_at);
    if (t !== 0) return t;
    return a.id.localeCompare(b.id);
  });
}

export function MissionTimeline({
  events,
  missionStatus,
  phaseLabel,
}: {
  events: MissionEvent[];
  /** Optional: tailor empty copy when the mission is waiting on governance. */
  missionStatus?: string;
  /** Derived operator phase (same as mission detail header) — empty timeline only. */
  phaseLabel?: string | null;
}) {
  const sorted = sortEventsChronological(events);

  if (sorted.length === 0) {
    const empty =
      phaseLabel?.trim()
        ? `No timeline events yet — ${phaseLabel.trim()}.`
        : missionStatus === "awaiting_approval"
          ? "Awaiting first execution update — approval may be pending."
          : "Awaiting first execution update";
    return <p className="text-xs leading-relaxed text-[var(--text-secondary)]">{empty}</p>;
  }

  return (
    <ul className="space-y-0">
      {sorted.map((ev, i) => {
        const p = ev.payload as Record<string, unknown> | null;
        const isLast = i === sorted.length - 1;
        const execMeta =
          ev.event_type === "receipt_recorded" && p && p.execution_meta != null
            ? p.execution_meta
            : null;
        const summaryText =
          p && typeof p.summary === "string" ? p.summary.trim() : "";
        return (
          <li key={ev.id} className="relative flex gap-3">
            <div className="flex w-4 shrink-0 flex-col items-center">
              <span
                className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[var(--accent-blue)]/80 ring-2 ring-[var(--accent-blue)]/20"
                aria-hidden
              />
              {!isLast ? (
                <span className="mt-0.5 min-h-[1.5rem] w-px flex-1 bg-[var(--bg-border)]" aria-hidden />
              ) : null}
            </div>
            <div className={`min-w-0 flex-1 pb-6 ${isLast ? "pb-0" : ""}`}>
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="font-display text-xs font-semibold text-[var(--text-primary)]">
                  {timelineEventTitle(ev)}
                </span>
                <span className="font-mono text-[10px] text-[var(--text-muted)]">
                  {formatRelativeTime(ev.created_at)}
                </span>
              </div>
              {ev.event_type === "mission_status_changed" && p ? (
                <p className="mt-1 font-mono text-xs text-[var(--text-secondary)]">
                  {typeof p.from === "string" ? p.from : "?"} → {typeof p.to === "string" ? p.to : "?"}
                </p>
              ) : null}
              {ev.event_type === "approval_requested" && p ? (
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  {typeof p.action_type === "string" ? p.action_type : null}
                  {typeof p.reason === "string" && String(p.reason).trim() ? ` — ${p.reason}` : null}
                </p>
              ) : null}
              {ev.event_type === "approval_resolved" && p ? (
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  {typeof p.decision === "string" ? p.decision : ""}
                  {typeof p.decided_by === "string" ? ` · ${p.decided_by}` : ""}
                </p>
              ) : null}
              {ev.event_type === "routing_decided" && p ? (
                (typeof p.reason_summary === "string" && String(p.reason_summary).trim()) ||
                p.pending_approval === true ? (
                  <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">
                    {typeof p.reason_summary === "string" && String(p.reason_summary).trim()
                      ? String(p.reason_summary).trim()
                      : null}
                    {p.pending_approval === true ? (
                      <span> Execution deferred pending approval.</span>
                    ) : null}
                  </p>
                ) : null
              ) : null}
              {ev.event_type === "receipt_recorded" && p ? (
                <div className="mt-2 space-y-2">
                  {summaryText ? (
                    <p className="text-sm leading-relaxed text-[var(--text-primary)]">{summaryText}</p>
                  ) : (
                    <p className="text-xs leading-relaxed text-[var(--text-muted)]">
                      {missionStatus === "failed"
                        ? operatorCopy.receiptNoSummaryFailed
                        : operatorCopy.receiptNoSummary}
                    </p>
                  )}
                  <ExecutionMetaLine value={execMeta} />
                </div>
              ) : null}
              {ev.event_type === "created" && p && typeof p.text === "string" ? (
                <p className="mt-1 line-clamp-3 text-xs text-[var(--text-secondary)]">{p.text}</p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
