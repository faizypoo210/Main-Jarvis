import { compactExecutionMeta, formatExecutionMetaParts } from "../../lib/missionExecutiveSummary";

/** Compact operator-facing execution metadata (lane / model / resumed flag). */
export function ExecutionMetaLine({ value }: { value: unknown }) {
  const meta = compactExecutionMeta(value);
  if (!meta) return null;
  const parts = formatExecutionMetaParts(meta);
  if (parts.length === 0) return null;
  return (
    <p className="mt-2 font-mono text-[10px] leading-relaxed text-[var(--text-muted)]">
      <span className="text-[var(--text-muted)]/90">{parts.join(" · ")}</span>
    </p>
  );
}
