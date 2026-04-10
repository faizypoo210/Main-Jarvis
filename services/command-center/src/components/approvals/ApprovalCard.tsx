import { RiskBadge, type Risk } from "../common/RiskBadge";
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
}: {
  approval: Approval;
  onApprove?: () => void | Promise<void>;
  onDeny?: () => void | Promise<void>;
  muted?: boolean;
  resolving?: boolean;
  resolveError?: string | null;
}) {
  const pending = approval.status === "pending";
  return (
    <article
      className={`rounded-xl border border-[var(--bg-border)] p-4 ${muted ? "opacity-70" : ""}`}
      style={{ backgroundColor: "var(--bg-surface)" }}
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 h-8 w-8 shrink-0 rounded-lg bg-[var(--accent-blue-glow)] ring-1 ring-[var(--accent-blue)]/25" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="font-display text-sm font-semibold text-[var(--text-primary)]">
              {approval.action_type}
            </h4>
            <RiskBadge risk={toRisk(approval.risk_class)} />
          </div>
          <p className="mt-1 font-mono text-[10px] text-[var(--text-muted)]">
            {new Date(approval.created_at).toLocaleString()} · {approval.requested_via}
          </p>
        </div>
      </div>
      {pending && onApprove && onDeny ? (
        <div className="mt-4 flex flex-col gap-2">
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              disabled={resolving}
              onClick={() => void onApprove()}
              className="min-h-[44px] min-w-[120px] rounded-lg border border-[var(--bg-border)] bg-transparent px-4 py-2 text-sm font-semibold text-[var(--text-secondary)] transition-opacity duration-150 ease-linear hover:bg-[var(--bg-elevated)]/60 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Approve
            </button>
            <button
              type="button"
              disabled={resolving}
              onClick={() => void onDeny()}
              className="min-h-[44px] min-w-[120px] rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white transition-opacity duration-150 ease-linear hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Deny
            </button>
          </div>
          {resolveError ? (
            <p className="text-xs text-[var(--status-red)]">Failed to resolve — try again</p>
          ) : null}
        </div>
      ) : (
        <p className="mt-3 text-xs text-[var(--text-secondary)]">
          {approval.status === "approved" ? "Approved" : approval.status} ·{" "}
          {approval.decided_at ? new Date(approval.decided_at).toLocaleString() : "—"}
        </p>
      )}
    </article>
  );
}
