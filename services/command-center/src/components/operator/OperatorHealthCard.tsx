import type { ReactNode } from "react";
import type { HealthState } from "../../lib/types";
import { healthDotClass, healthLabel } from "../../lib/operatorHealth";

export function OperatorHealthCard({
  title,
  status,
  detail,
  footer,
}: {
  title: string;
  status: HealthState;
  detail: string | null;
  footer?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)]/60 p-4">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-medium text-[var(--text-primary)]">{title}</h3>
        <span className="flex shrink-0 items-center gap-1.5">
          <span
            className={`h-2 w-2 rounded-full ${healthDotClass(status)}`}
            aria-hidden
          />
          <span className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
            {healthLabel(status)}
          </span>
        </span>
      </div>
      {detail ? (
        <p className="break-words text-[11px] leading-snug text-[var(--text-muted)]">{detail}</p>
      ) : null}
      {footer}
    </div>
  );
}
