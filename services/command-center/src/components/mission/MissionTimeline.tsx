import type { MissionEvent } from "../../lib/types";
import { formatRelativeTime } from "../../lib/format";
import { ExecutionMetaLine } from "./ExecutionMetaLine";
import { operatorCopy } from "../../lib/operatorCopy";

function timelineEventTitle(ev: MissionEvent): string {
  const p = ev.payload as Record<string, unknown> | null;
  if (ev.event_type === "memory_saved" && p) {
    const t = typeof p.title === "string" ? p.title.trim() : "";
    const sk = typeof p.source_kind === "string" ? p.source_kind : "";
    return t ? `Operator memory saved · ${t}${sk ? ` (${sk})` : ""}` : "Operator memory saved";
  }
  if (ev.event_type === "memory_promoted" && p) {
    const t = typeof p.title === "string" ? p.title.trim() : "";
    const sk = typeof p.source_kind === "string" ? p.source_kind : "";
    return t ? `Memory promoted · ${t}${sk ? ` · ${sk}` : ""}` : "Memory promoted";
  }
  if (ev.event_type === "memory_archived" && p) {
    const t = typeof p.title === "string" ? p.title.trim() : "";
    return t ? `Memory archived · ${t}` : "Memory archived";
  }
  if (ev.event_type === "integration_action_requested" && p) {
    const prov = typeof p.provider === "string" ? p.provider : "";
    if (prov === "gmail") {
      const subj = typeof p.subject === "string" ? p.subject.trim() : "";
      const tp = typeof p.to_preview === "string" ? p.to_preview : "";
      return tp || subj ? `Gmail draft requested · ${tp}${subj ? ` · ${subj}` : ""}` : "Gmail draft requested";
    }
    const repo = typeof p.repo === "string" ? p.repo : "";
    const title = typeof p.title === "string" ? p.title.trim() : "";
    return repo
      ? `GitHub issue requested · ${repo}${title ? ` · ${title}` : ""}`
      : "GitHub integration requested";
  }
  if (ev.event_type === "integration_action_executed" && p) {
    if (typeof p.provider === "string" && p.provider === "gmail") {
      const subj = typeof p.subject === "string" ? p.subject : "";
      const did = typeof p.draft_id === "string" ? p.draft_id : "";
      const gurl = typeof p.gmail_url === "string" ? p.gmail_url : "";
      return `Gmail draft saved${subj ? ` · ${subj}` : ""}${did ? ` · ${did}` : ""}${gurl ? ` · ${gurl}` : ""}`;
    }
    const repo = typeof p.repo === "string" ? p.repo : "";
    const n = p.issue_number;
    const url = typeof p.html_url === "string" ? p.html_url : "";
    const num = typeof n === "number" ? `#${n}` : "";
    return repo ? `GitHub issue created · ${repo} ${num}`.trim() + (url ? ` · ${url}` : "") : "GitHub issue created";
  }
  if (ev.event_type === "integration_action_failed" && p) {
    const prov = typeof p.provider === "string" ? p.provider : "";
    const code = typeof p.error_code === "string" ? p.error_code : "";
    const msg = typeof p.error_message === "string" ? p.error_message.slice(0, 160) : "";
    const prefix = prov === "gmail" ? "Gmail draft failed" : "GitHub action failed";
    return code ? `${prefix} · ${code}${msg ? ` — ${msg}` : ""}` : prefix;
  }
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
    case "integration_action_requested":
      return "Integration requested";
    case "integration_action_executed":
      return "Integration completed";
    case "integration_action_failed":
      return "Integration failed";
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
        const rt = p && typeof p.receipt_type === "string" ? p.receipt_type : "";
        const gh =
          p && typeof p.github === "object" && p.github !== null
            ? (p.github as Record<string, unknown>)
            : null;
        const gm =
          p && typeof p.gmail === "object" && p.gmail !== null
            ? (p.gmail as Record<string, unknown>)
            : null;
        const execMeta =
          ev.event_type === "receipt_recorded" &&
          p &&
          p.execution_meta != null &&
          rt === "openclaw_execution"
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
              {ev.event_type === "memory_saved" && p ? (
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  {typeof p.source_kind === "string" ? `Source: ${p.source_kind}` : null}
                </p>
              ) : null}
              {ev.event_type === "memory_promoted" && p ? (
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  {typeof p.source_kind === "string" ? `Source: ${p.source_kind}` : null}
                  {typeof p.source_receipt_id === "string" ? ` · receipt ${p.source_receipt_id.slice(0, 8)}…` : null}
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
                  {rt === "github_issue_created" || rt === "github_issue_failed" ? (
                    <div className="space-y-1 text-xs text-[var(--text-secondary)]">
                      <p className="font-mono text-[10px] text-[var(--text-muted)]">
                        {rt === "github_issue_created" ? "github_issue_created" : "github_issue_failed"}
                      </p>
                      {gh && typeof gh.repo === "string" ? (
                        <p>
                          <span className="text-[var(--text-muted)]">Repo:</span> {gh.repo}
                        </p>
                      ) : null}
                      {gh && typeof gh.issue_number === "number" ? (
                        <p>
                          <span className="text-[var(--text-muted)]">Issue:</span> #{gh.issue_number}
                        </p>
                      ) : null}
                      {gh && typeof gh.html_url === "string" && gh.html_url ? (
                        <a
                          href={gh.html_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[var(--accent-blue)] underline-offset-2 hover:underline"
                        >
                          {gh.html_url}
                        </a>
                      ) : null}
                    </div>
                  ) : null}
                  {rt === "gmail_draft_created" || rt === "gmail_draft_failed" ? (
                    <div className="space-y-1 text-xs text-[var(--text-secondary)]">
                      <p className="font-mono text-[10px] text-[var(--text-muted)]">
                        {rt === "gmail_draft_created" ? "gmail_draft_created" : "gmail_draft_failed"}
                      </p>
                      {gm && typeof gm.to_preview === "string" ? (
                        <p>
                          <span className="text-[var(--text-muted)]">To:</span> {gm.to_preview}
                        </p>
                      ) : null}
                      {gm && typeof gm.subject === "string" ? (
                        <p>
                          <span className="text-[var(--text-muted)]">Subject:</span> {gm.subject}
                        </p>
                      ) : null}
                      {gm && typeof gm.draft_id === "string" ? (
                        <p>
                          <span className="text-[var(--text-muted)]">Draft id:</span> {gm.draft_id}
                        </p>
                      ) : null}
                      {gm && typeof gm.gmail_url === "string" && gm.gmail_url ? (
                        <a
                          href={gm.gmail_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[var(--accent-blue)] underline-offset-2 hover:underline"
                        >
                          Open Gmail drafts
                        </a>
                      ) : null}
                    </div>
                  ) : null}
                  {summaryText ? (
                    <p className="text-sm leading-relaxed text-[var(--text-primary)]">{summaryText}</p>
                  ) : rt.startsWith("github_") || rt.startsWith("gmail_") ? null : (
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
