import { RiskBadge, type Risk } from "../common/RiskBadge";
import { approvalPostDecisionLine } from "../../lib/approvalPresentation";
import { operatorCopy } from "../../lib/operatorCopy";
import type { Approval } from "../../lib/types";

function toRisk(r: string): Risk {
  return r === "green" || r === "amber" || r === "red" ? r : "amber";
}

export function ApprovalCard({
  approval,
  onApprove,
  onDeny,
  muted,
  resolving,
  resolveError,
  recentlyResolvedDecision,
}: {
  approval: Approval;
  onApprove?: () => void | Promise<void>;
  onDeny?: () => void | Promise<void>;
  muted?: boolean;
  resolving?: boolean;
  resolveError?: string | null;
  /** Ephemeral: API succeeded but props still show pending (race). Suppresses repeat actions. */
  recentlyResolvedDecision?: "approved" | "denied" | null;
}) {
  const pending = approval.status === "pending";
  const showRaceSuccess = Boolean(pending && recentlyResolvedDecision != null && !resolving);
  const showPendingButtons = pending && onApprove && onDeny && !showRaceSuccess;

  return (
    <article
      className={`rounded-xl border border-[var(--bg-border)] p-4 ${muted ? "opacity-75" : ""}`}
      style={{ backgroundColor: "var(--bg-surface)" }}
      aria-busy={resolving === true ? "true" : undefined}
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 h-8 w-8 shrink-0 rounded-lg bg-[var(--accent-blue-glow)] ring-1 ring-[var(--accent-blue)]/25" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Governance
            </p>
            <RiskBadge risk={toRisk(approval.risk_class)} />
          </div>
          <h4 className="mt-1 font-display text-sm font-semibold text-[var(--text-primary)]">
            {approval.action_type}
          </h4>
          {approval.reason?.trim() ? (
            <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">{approval.reason}</p>
          ) : null}
          <p className="mt-2 font-mono text-[10px] text-[var(--text-muted)]">
            {new Date(approval.created_at).toLocaleString()} · {approval.requested_via}
          </p>
        </div>
      </div>
      {showRaceSuccess ? (
        <div className="mt-4 rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)]/80 px-3 py-2.5">
          <p className="text-xs font-medium text-[var(--text-secondary)]" role="status">
            {approvalPostDecisionLine(recentlyResolvedDecision!)}
          </p>
          <p className="mt-1 text-[10px] text-[var(--text-muted)]">{operatorCopy.approvalRefreshingState}</p>
        </div>
      ) : showPendingButtons ? (
        <div className="mt-4 flex flex-col gap-2">
          {resolving ? (
            <p className="text-xs text-[var(--text-muted)]" role="status" aria-live="polite">
              {operatorCopy.approvalRecording}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={resolving}
              aria-disabled={resolving === true}
              onClick={() => void onApprove()}
              className="min-h-[40px] min-w-[120px] rounded-lg border border-emerald-500/35 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200/95 transition-colors hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Approve
            </button>
            <button
              type="button"
              disabled={resolving}
              aria-disabled={resolving === true}
              onClick={() => void onDeny()}
              className="min-h-[40px] min-w-[120px] rounded-lg border border-[var(--bg-border)] bg-transparent px-4 py-2 text-sm font-semibold text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)]/60 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Deny
            </button>
          </div>
          {resolveError ? (
            <p className="text-xs text-[var(--status-red)]">{operatorCopy.approvalResolveFailed}</p>
          ) : null}
        </div>
      ) : (
        <div className="mt-4 rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)]/80 px-3 py-2.5">
          <p className="text-center text-xs font-medium text-[var(--text-secondary)]">
            {approval.status === "approved" ? "Approved" : approval.status === "denied" ? "Denied" : approval.status}
            {approval.decided_at ? (
              <span className="mt-1 block font-mono text-[10px] font-normal text-[var(--text-muted)]">
                {new Date(approval.decided_at).toLocaleString()}
              </span>
            ) : null}
          </p>
        </div>
      )}
    </article>
  );
}
