/**
 * Placeholder route — receipts will be loaded from the control plane next.
 */
const PLACEHOLDER_ROWS = [
  { id: "1", title: "Execution receipt (sample)", meta: "Pending wiring" },
  { id: "2", title: "Integration receipt (sample)", meta: "Pending wiring" },
  { id: "3", title: "Governed action receipt (sample)", meta: "Pending wiring" },
];

export function Receipts() {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="shrink-0 border-b border-[var(--bg-border)] px-4 py-3 md:px-6">
        <p className="font-mono text-xs text-[var(--text-muted)]">
          {PLACEHOLDER_ROWS.length} placeholder rows
        </p>
        <h2 className="mt-1 font-display text-base font-semibold text-[var(--text-primary)]">Receipts</h2>
        <p className="mt-1 max-w-xl text-xs text-[var(--text-secondary)]">
          Global receipt inbox will list execution and integration receipts here. No API calls yet.
        </p>
      </div>
      <ul className="min-h-0 flex-1 divide-y divide-[var(--bg-border)] overflow-y-auto">
        {PLACEHOLDER_ROWS.map((row) => (
          <li
            key={row.id}
            className="flex flex-col gap-1 bg-[var(--bg-void)] px-4 py-4 md:px-6"
          >
            <span className="text-sm font-medium text-[var(--text-primary)]">{row.title}</span>
            <span className="font-mono text-[10px] text-[var(--text-muted)]">{row.meta}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
