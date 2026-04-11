import { ExternalLink } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { RiskBadge, type Risk } from "../common/RiskBadge";
import type { Approval } from "../../lib/types";

function toRisk(r: string): Risk {
  return r === "green" || r === "amber" || r === "red" ? r : "amber";
}

export function InlineApprovalCard({
  approval,
  missionId,
  onApprove,
  onDeny,
  resolving,
  resolveError,
}: {
  approval: Approval;
  missionId: string;
  onApprove: () => void | Promise<void>;
  onDeny: () => void | Promise<void>;
  resolving?: boolean;
  resolveError?: string | null;
}) {
  const navigate = useNavigate();
  const pending = approval.status === "pending";

  return (
    <div
      className="ml-0 max-w-[min(100%,28rem)] rounded-xl border border-[var(--bg-border)] px-4 py-3.5"
      style={{ backgroundColor: "var(--bg-surface)" }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Governance
            </p>
            <RiskBadge risk={toRisk(approval.risk_class)} />
          </div>
          <p className="mt-2 font-display text-sm font-semibold leading-snug text-[var(--text-primary)]">
            {approval.action_type}
          </p>
          {approval.reason?.trim() ? (
            <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">{approval.reason}</p>
          ) : null}
          <p className="mt-2 font-mono text-[10px] text-[var(--text-muted)]">
            Mission {missionId.slice(0, 8)}… · {approval.requested_via}
          </p>
        </div>
      </div>
      {pending ? (
        <div className="mt-4 flex flex-col gap-2">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={resolving}
              onClick={() => void onApprove()}
              className="min-h-[40px] rounded-lg border border-emerald-500/35 bg-emerald-500/10 px-4 py-2 text-xs font-semibold text-emerald-200/95 transition-colors hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Approve
            </button>
            <button
              type="button"
              disabled={resolving}
              onClick={() => void onDeny()}
              className="min-h-[40px] rounded-lg border border-[var(--bg-border)] bg-transparent px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)]/60 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Deny
            </button>
            <button
              type="button"
              onClick={() => navigate(`/missions/${encodeURIComponent(missionId)}`)}
              className="inline-flex min-h-[40px] items-center gap-1 rounded-lg border border-transparent px-3 py-2 text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
            >
              Inspect
              <ExternalLink className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
          {resolveError ? (
            <p className="text-xs text-[var(--status-red)]">Could not update approval. Try again.</p>
          ) : null}
        </div>
      ) : (
        <div className="mt-4 rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)]/80 px-3 py-2">
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
    </div>
  );
}
