import { ApprovalCard } from "./ApprovalCard";
import type { Approval } from "../../lib/types";

export function ApprovalInbox({
  approvals,
  onApprove,
  onDeny,
  resolvingId,
  resolveErrorId,
}: {
  approvals: Approval[];
  onApprove?: (id: string) => void | Promise<void>;
  onDeny?: (id: string) => void | Promise<void>;
  resolvingId?: string | null;
  resolveErrorId?: string | null;
}) {
  return (
    <div className="flex flex-col gap-3">
      {approvals.map((a) => (
        <ApprovalCard
          key={a.id}
          approval={a}
          muted={a.status !== "pending"}
          resolving={resolvingId === a.id}
          resolveError={resolveErrorId === a.id ? "err" : null}
          onApprove={a.status === "pending" && onApprove ? () => onApprove(a.id) : undefined}
          onDeny={a.status === "pending" && onDeny ? () => onDeny(a.id) : undefined}
        />
      ))}
    </div>
  );
}
