import { useCallback, useState } from "react";
import { AlertTriangle, MoreHorizontal, Search } from "lucide-react";
import * as api from "../../lib/api";
import { usePendingApprovals } from "../../hooks/useControlPlane";
import { ApprovalCard } from "../approvals/ApprovalCard";

export function RightPanel({ onClose }: { onClose?: () => void }) {
  const { approvals, loading, refetch } = usePendingApprovals();
  const first = approvals[0];
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

  return (
    <aside
      className="flex h-full w-full flex-col border-l border-[var(--bg-border)] lg:w-[320px] lg:shrink-0"
      style={{ backgroundColor: "var(--bg-surface)" }}
    >
      <div className="flex items-center justify-between border-b border-[var(--bg-border)] px-4 py-3">
        <h2 className="font-display text-sm font-semibold text-[var(--text-primary)]">Offsite Details</h2>
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="rounded-lg p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
            aria-label="Search"
          >
            <Search className="h-4 w-4" />
          </button>
          <button
            type="button"
            className="rounded-lg p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
            aria-label="Options"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
          {onClose ? (
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] lg:hidden"
              aria-label="Close panel"
            >
              ×
            </button>
          ) : null}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <section className="mb-6">
          <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Basic fields
          </h3>
          <div className="space-y-3 text-sm">
            <div>
              <p className="text-[10px] text-[var(--text-muted)]">Venue</p>
              <p className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)] px-3 py-2 text-[var(--text-secondary)]">
                TBD
              </p>
            </div>
            <div>
              <p className="text-[10px] text-[var(--text-muted)]">Dates</p>
              <p className="text-[var(--text-primary)]">June 15–17</p>
            </div>
            <div>
              <p className="text-[10px] text-[var(--text-muted)]">Schedule</p>
              <p className="text-[var(--text-secondary)]">Draft agenda attached to mission.</p>
            </div>
          </div>
        </section>

        <section className="mb-6 rounded-lg border border-[var(--status-amber)]/30 bg-[var(--status-amber)]/5 p-3">
          <div className="flex items-center gap-2 text-[var(--status-amber)]">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span className="text-xs font-semibold">Commences</span>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">
            Confirm deposit window with venue before sending invites. Cancellation policy applies after booking
            confirmation.
          </p>
        </section>

        <section className="mb-6">
          <div className="mb-3 flex items-center gap-2">
            <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Approvals
            </h3>
            <span className="rounded-full bg-[var(--status-amber)]/20 px-2 py-0.5 text-[10px] font-bold text-[var(--status-amber)]">
              {loading && approvals.length === 0 ? "…" : approvals.length}
            </span>
          </div>
          {first && first.status === "pending" ? (
            <ApprovalCard
              approval={first}
              resolving={resolvingId === first.id}
              resolveError={resolveErrorId === first.id ? "err" : null}
              onApprove={() => resolve(first.id, "approved")}
              onDeny={() => resolve(first.id, "denied")}
            />
          ) : (
            <p className="text-xs text-[var(--text-muted)]">No pending approvals</p>
          )}
        </section>

        <section>
          <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Recent activity
          </h3>
          <ul className="space-y-3 text-xs text-[var(--text-secondary)]">
            <li className="flex gap-2">
              <span className="text-[var(--text-muted)]">•</span>
              <span>
                Venue shortlist generated <span className="font-mono text-[10px] text-[var(--text-muted)]">10:02</span>
              </span>
            </li>
            <li className="flex gap-2">
              <span className="text-[var(--text-muted)]">•</span>
              <span>
                Calendar hold requested <span className="font-mono text-[10px] text-[var(--text-muted)]">10:05</span>
              </span>
            </li>
            <li className="flex gap-2">
              <span className="text-[var(--text-muted)]">•</span>
              <span>
                Invites draft ready <span className="font-mono text-[10px] text-[var(--text-muted)]">10:08</span>
              </span>
            </li>
          </ul>
        </section>
      </div>
    </aside>
  );
}
