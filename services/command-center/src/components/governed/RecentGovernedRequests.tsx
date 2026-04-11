import { Link } from "react-router-dom";
import type { Approval, GovernedActionCatalogResponse } from "../../lib/types";
import { formatRelativeTime } from "../../lib/format";
import {
  humanizeRequestedVia,
  isGovernedApprovalActionType,
  labelForApprovalActionType,
} from "../../lib/governedCatalogPresentation";

function statusLine(a: Approval): string {
  if (a.status === "pending") return "Awaiting approval";
  if (a.status === "approved") return "Approved";
  if (a.status === "denied") return "Denied";
  return a.status;
}

export function RecentGovernedRequests({
  approvals,
  catalog,
}: {
  approvals: Approval[];
  catalog: GovernedActionCatalogResponse | null;
}) {
  const rows = [...approvals]
    .filter((a) => isGovernedApprovalActionType(a.action_type))
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 5);

  if (rows.length === 0) {
    return null;
  }

  return (
    <section className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/30 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Recent governed requests
        </h2>
        <Link
          to="/approvals"
          className="text-[10px] font-medium text-[var(--accent-blue)] hover:underline"
        >
          Approvals queue
        </Link>
      </div>
      <ul className="mt-3 space-y-2">
        {rows.map((a) => (
          <li
            key={a.id}
            className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-[var(--bg-border)]/80 bg-[var(--bg-void)]/40 px-3 py-2"
          >
            <div className="min-w-0 flex-1">
              <p className="font-display text-xs font-semibold text-[var(--text-primary)]">
                {labelForApprovalActionType(a.action_type, catalog)}
              </p>
              <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">
                {statusLine(a)} · via {humanizeRequestedVia(a.requested_via)} ·{" "}
                {formatRelativeTime(a.created_at)}
              </p>
            </div>
            <Link
              to={`/approvals?approval=${encodeURIComponent(a.id)}`}
              className="shrink-0 text-[10px] font-medium text-[var(--accent-blue)] hover:underline"
            >
              Review
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
