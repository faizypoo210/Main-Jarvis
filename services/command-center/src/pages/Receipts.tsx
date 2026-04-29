import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/api";
import type { Mission, Receipt } from "../lib/types";
import { formatRelativeTime } from "../lib/format";
import { deriveReceiptPresentation } from "../lib/receiptPresentation";
import { operatorCopy } from "../lib/operatorCopy";
import { ExecutionMetaLine } from "../components/mission/ExecutionMetaLine";

/** Stub mission so `deriveReceiptPresentation` uses neutral empty-summary copy (status ≠ failed). */
const GLOBAL_RECEIPTS_MISSION_CONTEXT: Mission = {
  id: "00000000-0000-0000-0000-000000000000",
  title: "",
  description: null,
  status: "complete",
  priority: "normal",
  created_by: "system",
  surface_origin: null,
  risk_class: null,
  current_stage: null,
  summary: null,
  created_at: "1970-01-01T00:00:00.000Z",
  updated_at: "1970-01-01T00:00:00.000Z",
};

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

function GlobalReceiptRow({ receipt }: { receipt: Receipt }) {
  const p = deriveReceiptPresentation(GLOBAL_RECEIPTS_MISSION_CONTEXT, receipt);
  const mid = receipt.mission_id?.trim() ?? "";

  const headline = (
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <span className="font-display text-sm font-semibold text-[var(--text-primary)]">{p.receiptType}</span>
      <time className="font-mono text-[10px] text-[var(--text-muted)]" dateTime={p.createdAt}>
        {formatRelativeTime(p.createdAt)}
      </time>
    </div>
  );

  return (
    <li className="border-b border-[var(--bg-border)] bg-[var(--bg-void)] px-4 py-4 md:px-6">
      {mid ? (
        <Link
          to={`/missions/${encodeURIComponent(mid)}`}
          className="block rounded-md outline-none ring-offset-2 ring-offset-[var(--bg-void)] focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)]"
        >
          {headline}
        </Link>
      ) : (
        headline
      )}
      <p className="mt-1 font-mono text-[10px] text-[var(--text-muted)]">{p.source}</p>
      <p className="mt-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {p.summaryPlain ?? p.emptySummaryFallback}
      </p>
      <ExecutionMetaLine value={p.executionMeta} />
      <ReceiptPayloadInspect payload={p.payloadRecord} />
    </li>
  );
}

export function Receipts() {
  const [rows, setRows] = useState<Receipt[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    setError(null);
    void (async () => {
      try {
        const list = await api.getReceipts({ limit: 50 });
        if (!cancelled) {
          setRows(list);
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const loading = rows === null && error === null;
  const empty = rows !== null && rows.length === 0;
  const countLabel = loading || error ? "—" : empty ? "0 receipts" : `${rows!.length} shown`;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      {error ? (
        <div
          className="shrink-0 border-b border-[var(--status-amber)]/30 bg-[var(--status-amber)]/10 px-4 py-2 text-center text-xs text-[var(--status-amber)] md:px-6"
          role="status"
        >
          {error}
        </div>
      ) : null}
      <div className="shrink-0 border-b border-[var(--bg-border)] px-4 py-3 md:px-6">
        <p className="font-mono text-xs text-[var(--text-muted)]">{countLabel}</p>
        <h2 className="mt-1 font-display text-base font-semibold text-[var(--text-primary)]">Receipts</h2>
        <p className="mt-1 max-w-xl text-xs text-[var(--text-secondary)]">
          Global receipt inbox — execution and integration receipts from the control plane.
        </p>
      </div>
      {loading ? (
        <div className="flex flex-1 flex-col px-4 py-6 md:px-6">
          <p className="text-xs text-[var(--text-muted)]">Loading receipts…</p>
        </div>
      ) : empty ? (
        <div className="flex flex-1 flex-col px-4 py-6 md:px-6">
          <p className="text-xs text-[var(--text-secondary)]">
            No receipts yet. Receipts appear here after missions run.
          </p>
        </div>
      ) : rows && rows.length > 0 ? (
        <ul className="min-h-0 flex-1 divide-y divide-[var(--bg-border)] overflow-y-auto">
          {rows.map((r) => (
            <GlobalReceiptRow key={r.id} receipt={r} />
          ))}
        </ul>
      ) : null}
    </div>
  );
}
