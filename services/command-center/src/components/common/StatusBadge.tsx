type Status = "pending" | "active" | "blocked" | "awaiting_approval" | "complete" | "failed";

const styles: Record<
  Status,
  { dot: string; label: string; bg: string }
> = {
  pending: {
    dot: "bg-[var(--text-muted)]",
    label: "text-[var(--text-muted)]",
    bg: "bg-[var(--bg-border)]",
  },
  active: {
    dot: "bg-[var(--status-blue)]",
    label: "text-[var(--status-blue)]",
    bg: "bg-[var(--status-blue)]/15",
  },
  blocked: {
    dot: "bg-[var(--status-red)]",
    label: "text-[var(--status-red)]",
    bg: "bg-[var(--status-red)]/15",
  },
  awaiting_approval: {
    dot: "bg-[var(--status-amber)]",
    label: "text-[var(--status-amber)]",
    bg: "bg-[var(--status-amber)]/15",
  },
  complete: {
    dot: "bg-[var(--status-green)]",
    label: "text-[var(--status-green)]",
    bg: "bg-[var(--status-green)]/15",
  },
  failed: {
    dot: "bg-[var(--status-red)]",
    label: "text-[var(--status-red)]",
    bg: "bg-[var(--status-red)]/15",
  },
};

const display: Record<Status, string> = {
  pending: "Pending",
  active: "Active",
  blocked: "Blocked",
  awaiting_approval: "Awaiting approval",
  complete: "Complete",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: Status }) {
  const s = styles[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${s.bg}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden />
      <span className={s.label}>{display[status]}</span>
    </span>
  );
}
