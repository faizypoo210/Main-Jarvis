import { ExternalLink } from "lucide-react";
import { RiskBadge, type Risk } from "../common/RiskBadge";
import type { Approval } from "../../lib/types";

function toRisk(r: string): Risk {
  return r === "green" || r === "amber" || r === "red" ? r : "amber";
}

/**
 * Spoken-ready governance summary for voice; Approve/Deny use the same control-plane endpoints as the rest of the app.
 */
export function VoiceApprovalBrief({
  approval,
  otherPendingCount,
  onViewMission,
  onApprove,
  onDeny,
  resolving,
  resolveError,
}: {
  approval: Approval;
  /** Pending approvals on other missions (informational). */
  otherPendingCount: number;
  onViewMission: () => void;
  onApprove: () => void | Promise<void>;
  onDeny: () => void | Promise<void>;
  resolving?: boolean;
  resolveError?: boolean;
}) {
  const reason = approval.reason?.trim();

  return (
    <div className="mt-6 w-full max-w-md rounded-xl border border-white/10 bg-white/[0.06] px-4 py-3 text-left shadow-[0_0_0_1px_rgba(255,255,255,0.04)]">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-white/50">Governance</p>
      <p className="mt-1.5 font-display text-sm font-semibold leading-snug text-white">{approval.action_type}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <RiskBadge risk={toRisk(approval.risk_class)} />
        <span className="font-mono text-[10px] text-white/45">{approval.requested_via}</span>
      </div>
      {reason ? <p className="mt-2 text-xs leading-relaxed text-white/80">{reason}</p> : null}
      {otherPendingCount > 0 ? (
        <p className="mt-2 text-[10px] text-white/45">
          {otherPendingCount === 1
            ? "One more approval pending elsewhere."
            : `${otherPendingCount} more approvals pending elsewhere.`}
        </p>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onViewMission}
          className="inline-flex items-center gap-1 rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-xs font-medium text-white/90 hover:bg-white/10"
        >
          View mission
          <ExternalLink className="h-3.5 w-3.5 opacity-70" aria-hidden />
        </button>
        <button
          type="button"
          disabled={resolving}
          onClick={() => void onApprove()}
          className="rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-3 py-2 text-xs font-semibold text-emerald-100/95 hover:bg-emerald-500/25 disabled:opacity-50"
        >
          Approve
        </button>
        <button
          type="button"
          disabled={resolving}
          onClick={() => void onDeny()}
          className="rounded-lg border border-white/15 bg-transparent px-3 py-2 text-xs font-semibold text-white/75 hover:bg-white/5 disabled:opacity-50"
        >
          Deny
        </button>
      </div>
      {resolveError ? (
        <p className="mt-2 text-xs text-red-400/90">Could not record decision. Try again.</p>
      ) : null}
    </div>
  );
}
