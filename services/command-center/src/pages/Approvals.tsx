import { useCallback, useEffect, useState } from "react";
import { ApprovalReviewPanel } from "../components/approvals/ApprovalReviewPanel";
import { RiskBadge, type Risk } from "../components/common/RiskBadge";
import {
  useApprovalBundle,
  usePendingApprovals,
  useResolveApprovalAction,
} from "../hooks/useControlPlane";

function toRisk(r: string): Risk {
  return r === "green" || r === "amber" || r === "red" ? r : "amber";
}

export function Approvals() {
  const { approvals, loading, error } = usePendingApprovals();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { bundle, loading: bundleLoading, error: bundleError, refetch: refetchBundle } =
    useApprovalBundle(selectedId);
  const { resolve, resolvingApprovalId, resolveErrorApprovalId, recentlyResolvedDecisionFor } =
    useResolveApprovalAction();

  useEffect(() => {
    if (!approvals.length) {
      setSelectedId(null);
      return;
    }
    setSelectedId((prev) => {
      if (prev && approvals.some((a) => a.id === prev)) return prev;
      return approvals[0]?.id ?? null;
    });
  }, [approvals]);

  const selected = approvals.find((a) => a.id === selectedId) ?? null;

  const onApprove = useCallback(() => {
    if (!selectedId) return;
    void resolve(selectedId, "approved", { onSuccess: () => void refetchBundle() });
  }, [selectedId, resolve, refetchBundle]);

  const onDeny = useCallback(() => {
    if (!selectedId) return;
    void resolve(selectedId, "denied", { onSuccess: () => void refetchBundle() });
  }, [selectedId, resolve, refetchBundle]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-[var(--bg-border)] px-4 py-3 md:px-6">
        <span className="rounded-full bg-[var(--status-amber)]/20 px-2.5 py-0.5 text-xs font-bold text-[var(--status-amber)]">
          {loading && approvals.length === 0 ? "…" : approvals.length} pending
        </span>
        <p className="text-xs text-[var(--text-muted)]">
          Select an approval to inspect the structured review packet before deciding.
        </p>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden px-4 py-4 md:flex-row md:px-6">
        <aside className="flex w-full shrink-0 flex-col gap-1 overflow-y-auto md:w-72 md:max-w-[20rem]">
          {error && approvals.length === 0 ? (
            <p className="text-center text-sm text-[var(--text-muted)]">Could not load approvals.</p>
          ) : approvals.length === 0 && !loading ? (
            <p className="text-sm text-[var(--text-muted)]">No pending approvals.</p>
          ) : (
            approvals.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => setSelectedId(a.id)}
                className={`rounded-lg border px-3 py-2.5 text-left transition-colors ${
                  selectedId === a.id
                    ? "border-[var(--accent-blue)]/50 bg-[var(--bg-elevated)]/80 ring-1 ring-[var(--accent-blue)]/25"
                    : "border-[var(--bg-border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)]/50"
                }`}
              >
                <div className="flex items-center gap-2">
                  <RiskBadge risk={toRisk(a.risk_class)} />
                  <span className="min-w-0 flex-1 truncate font-display text-xs font-semibold text-[var(--text-primary)]">
                    {a.action_type}
                  </span>
                </div>
                {a.reason?.trim() ? (
                  <p className="mt-1 line-clamp-2 text-[10px] leading-snug text-[var(--text-muted)]">
                    {a.reason}
                  </p>
                ) : null}
                <p className="mt-1 font-mono text-[9px] text-[var(--text-muted)]">
                  {new Date(a.created_at).toLocaleString()}
                </p>
              </button>
            ))
          )}
        </aside>
        <section className="min-h-[320px] min-w-0 flex-1 md:min-h-0">
          {selected ? (
            <ApprovalReviewPanel
              bundle={bundle}
              loading={bundleLoading}
              error={bundleError}
              approval={selected}
              onApprove={onApprove}
              onDeny={onDeny}
              resolving={resolvingApprovalId === selected.id}
              resolveError={resolveErrorApprovalId === selected.id ? "err" : null}
              recentlyResolvedDecision={
                selected.status === "pending" ? recentlyResolvedDecisionFor(selected.id) : null
              }
            />
          ) : (
            <div
              className="flex h-full min-h-[240px] items-center justify-center rounded-xl border border-dashed border-[var(--bg-border)] px-4 text-center text-sm text-[var(--text-muted)]"
              style={{ backgroundColor: "var(--bg-surface)" }}
            >
              {loading ? "Loading…" : "Select a pending approval to review."}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
