export type Risk = "green" | "amber" | "red";

const map: Record<Risk, { border: string; text: string; label: string }> = {
  green: {
    border: "border-[var(--status-green)]/40",
    text: "text-[var(--status-green)]",
    label: "Green",
  },
  amber: {
    border: "border-[var(--status-amber)]/40",
    text: "text-[var(--status-amber)]",
    label: "Amber",
  },
  red: {
    border: "border-[var(--status-red)]/40",
    text: "text-[var(--status-red)]",
    label: "Red",
  },
};

export function RiskBadge({ risk }: { risk: Risk }) {
  const m = map[risk];
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${m.border} ${m.text}`}
    >
      {m.label}
    </span>
  );
}
