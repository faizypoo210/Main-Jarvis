import { useCallback, useState } from "react";
import * as api from "../lib/api";
import { ApprovalInbox } from "../components/approvals/ApprovalInbox";
import { usePendingApprovals } from "../hooks/useControlPlane";

export function Approvals() {
  const { approvals, loading, error, refetch } = usePendingApprovals();
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

  const onApprove = useCallback((id: string) => resolve(id, "approved"), [resolve]);
  const onDeny = useCallback((id: string) => resolve(id, "denied"), [resolve]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-[var(--bg-border)] px-4 py-3 md:px-6">
        <span className="rounded-full bg-[var(--status-amber)]/20 px-2.5 py-0.5 text-xs font-bold text-[var(--status-amber)]">
          {loading && approvals.length === 0 ? "…" : approvals.length} pending
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-6">
        {error && approvals.length === 0 ? (
          <p className="text-center text-sm text-[var(--text-muted)]">Could not load approvals.</p>
        ) : (
          <ApprovalInbox
            approvals={approvals}
            onApprove={onApprove}
            onDeny={onDeny}
            resolvingId={resolvingId}
            resolveErrorId={resolveErrorId}
          />
        )}
      </div>
    </div>
  );
}
