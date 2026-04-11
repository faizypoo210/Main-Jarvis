import type { Mission, Receipt } from "../../lib/types";
import { receiptAnchorDomId, type LatestExecutionResult } from "../../lib/missionLatestResult";
import { operatorCopy } from "../../lib/operatorCopy";
import {
  compactReceiptPreview,
  deriveReceiptPresentation,
  selectPrimaryReceipt,
  sortReceiptsNewestFirst,
} from "../../lib/receiptPresentation";
import { formatRelativeTime } from "../../lib/format";
import { ExecutionMetaLine } from "./ExecutionMetaLine";

function ReceiptPayloadInspect({ payload }: { payload: Record<string, unknown> }) {
  const json = JSON.stringify(payload, null, 2);
  return (
    <details className="mt-3 rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)]/40">
      <summary className="cursor-pointer select-none px-3 py-2 text-[10px] font-medium text-[var(--text-muted)] transition-colors hover:text-[var(--text-secondary)] [&::-webkit-details-marker]:hidden">
        {operatorCopy.receiptInspectPayload}
      </summary>
      <pre
        className="max-h-[min(40vh,22rem)] overflow-auto border-t border-[var(--bg-border)] p-3 font-mono text-[10px] leading-relaxed text-[var(--text-secondary)]"
        tabIndex={0}
      >
        {json}
      </pre>
    </details>
  );
}

function ReceiptPrimaryCard({ mission, receipt }: { mission: Mission; receipt: Receipt }) {
  const p = deriveReceiptPresentation(mission, receipt);
  return (
    <article
      id={receiptAnchorDomId(receipt.id)}
      className="scroll-mt-24 rounded-xl border border-[var(--accent-blue)]/25 px-4 py-4 shadow-[inset_0_1px_0_0_rgba(59,130,246,0.06)]"
      style={{ backgroundColor: "var(--bg-surface)" }}
      aria-label="Newest receipt"
    >
      <p className="text-[9px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
        {operatorCopy.receiptPrimaryBadge}
      </p>
      <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-display text-sm font-semibold text-[var(--text-primary)]">{p.receiptType}</span>
        <time className="font-mono text-[10px] text-[var(--text-muted)]" dateTime={p.createdAt}>
          {formatRelativeTime(p.createdAt)}
        </time>
      </div>
      <p className="mt-1 font-mono text-[10px] text-[var(--text-muted)]">{p.source}</p>
      <p className="mt-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {p.summaryPlain ?? p.emptySummaryFallback}
      </p>
      <ExecutionMetaLine value={p.executionMeta} />
      <ReceiptPayloadInspect payload={p.payloadRecord} />
    </article>
  );
}

function ReceiptOlderRow({ mission, receipt }: { mission: Mission; receipt: Receipt }) {
  const p = deriveReceiptPresentation(mission, receipt);
  const preview = compactReceiptPreview(p);
  return (
    <li id={receiptAnchorDomId(receipt.id)} className="scroll-mt-20">
      <details className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-surface)]">
        <summary className="flex cursor-pointer list-none flex-wrap items-baseline gap-x-2 gap-y-1 px-3 py-2.5 text-left [&::-webkit-details-marker]:hidden">
          <span className="font-display text-xs font-semibold text-[var(--text-primary)]">{p.receiptType}</span>
          <span className="font-mono text-[10px] text-[var(--text-muted)]">{formatRelativeTime(p.createdAt)}</span>
          <span className="w-full min-w-0 pl-0 text-[10px] leading-snug text-[var(--text-muted)] sm:w-auto sm:flex-1 sm:pl-2">
            {preview}
          </span>
        </summary>
        <div className="border-t border-[var(--bg-border)] px-3 py-3">
          <p className="font-mono text-[10px] text-[var(--text-muted)]">{p.source}</p>
          <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
            {p.summaryPlain ?? p.emptySummaryFallback}
          </p>
          <ExecutionMetaLine value={p.executionMeta} />
          <ReceiptPayloadInspect payload={p.payloadRecord} />
        </div>
      </details>
    </li>
  );
}

export function MissionReceiptsSection({
  mission,
  receipts,
  loading,
  latestExecution,
}: {
  mission: Mission | null;
  receipts: Receipt[];
  loading: boolean;
  latestExecution: LatestExecutionResult | null;
}) {
  if (loading && receipts.length === 0) {
    return <p className="text-xs text-[var(--text-muted)]">Loading…</p>;
  }
  if (receipts.length === 0) {
    return <p className="text-xs text-[var(--text-secondary)]">No receipts yet.</p>;
  }
  if (!mission) {
    return <p className="text-xs text-[var(--text-muted)]">Loading…</p>;
  }

  const sorted = sortReceiptsNewestFirst(receipts);
  const { primary, older } = selectPrimaryReceipt(sorted, latestExecution);

  return (
    <div className="space-y-5">
      <ReceiptPrimaryCard mission={mission} receipt={primary} />
      {older.length > 0 ? (
        <div>
          <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            {operatorCopy.receiptEarlierHeading}{" "}
            <span className="font-normal text-[var(--text-muted)]">({older.length})</span>
          </h3>
          <ul className="space-y-2">
            {older.map((r) => (
              <ReceiptOlderRow key={r.id} mission={mission} receipt={r} />
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
