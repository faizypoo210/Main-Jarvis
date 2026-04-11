import type { StreamPhase } from "../../contexts/ControlPlaneLiveContext";

export function LiveLinkIndicator({
  phase,
  alwaysVisible,
}: {
  phase: StreamPhase;
  /** When true, show on narrow viewports (e.g. mission inspection header). */
  alwaysVisible?: boolean;
}) {
  const dot =
    phase === "live"
      ? "bg-emerald-500/90 shadow-[0_0_8px_rgba(52,211,153,0.35)]"
      : phase === "reconnecting"
        ? "bg-amber-500/85 shadow-[0_0_8px_rgba(245,158,11,0.25)]"
        : "bg-[var(--text-muted)]/50";
  const label =
    phase === "live" ? "Live" : phase === "reconnecting" ? "Reconnecting" : "Offline";

  return (
    <div
      className={`${alwaysVisible ? "flex" : "hidden lg:flex"} items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-[var(--text-muted)]`}
      title="Control plane update stream"
    >
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} aria-hidden />
      <span>{label}</span>
    </div>
  );
}
