import { Link } from "react-router-dom";
import { RiskBadge, type Risk } from "../common/RiskBadge";
import { approvalPostDecisionLine } from "../../lib/approvalPresentation";
import { operatorCopy } from "../../lib/operatorCopy";
import type { Approval, ApprovalBundleResponse } from "../../lib/types";

function toRisk(r: string): Risk {
  return r === "green" || r === "amber" || r === "red" ? r : "amber";
}

function formatAgeSeconds(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  if (s < 86400) return `${(s / 3600).toFixed(1)}h`;
  return `${(s / 86400).toFixed(1)}d`;
}

export function ApprovalReviewPanel({
  bundle,
  loading,
  error,
  approval,
  onApprove,
  onDeny,
  resolving,
  resolveError,
  recentlyResolvedDecision,
}: {
  bundle: ApprovalBundleResponse | null;
  loading: boolean;
  error: string | null;
  approval: Approval;
  onApprove?: () => void | Promise<void>;
  onDeny?: () => void | Promise<void>;
  resolving?: boolean;
  resolveError?: string | null;
  recentlyResolvedDecision?: "approved" | "denied" | null;
}) {
  const pending = approval.status === "pending";
  const showRaceSuccess = Boolean(pending && recentlyResolvedDecision != null && !resolving);
  const showPendingButtons = pending && onApprove && onDeny && !showRaceSuccess;

  const pk = bundle?.packet;

  return (
    <div
      className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-[var(--bg-border)]"
      style={{ backgroundColor: "var(--bg-surface)" }}
    >
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-5">
        {loading && !bundle ? (
          <p className="text-sm text-[var(--text-muted)]">Loading review packet…</p>
        ) : error ? (
          <p className="text-sm text-[var(--status-red)]">{error}</p>
        ) : (
          <>
            {pk ? (
              <div className="space-y-4">
                <header className="space-y-2 border-b border-[var(--bg-border)] pb-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                      Review packet
                    </p>
                    <RiskBadge risk={toRisk(approval.risk_class)} />
                    {pk.identity_bearing ? (
                      <span className="rounded px-1.5 py-0.5 text-[10px] font-medium uppercase text-[var(--text-muted)] ring-1 ring-[var(--bg-border)]">
                        Identity-bearing
                      </span>
                    ) : null}
                    {!pk.parse_ok ? (
                      <span className="rounded bg-[var(--status-amber)]/15 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--status-amber)]">
                        Parse issue
                      </span>
                    ) : null}
                  </div>
                  <h2 className="font-display text-lg font-semibold text-[var(--text-primary)]">
                    {pk.headline}
                  </h2>
                  {pk.subheadline ? (
                    <p className="text-sm text-[var(--text-secondary)]">{pk.subheadline}</p>
                  ) : null}
                  <p className="text-sm leading-relaxed text-[var(--text-secondary)]">{pk.brief_summary}</p>
                  <p className="rounded-lg bg-[var(--bg-void)]/80 px-3 py-2.5 text-xs leading-relaxed text-[var(--text-muted)] ring-1 ring-[var(--bg-border)]">
                    <span className="font-medium text-[var(--text-secondary)]">Read aloud cue: </span>
                    {pk.spoken_summary}
                  </p>
                </header>

                {bundle?.context ? (
                  <section className="space-y-2 text-xs">
                    <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                      Decision context
                    </h3>
                    <div className="grid gap-1.5 text-[var(--text-secondary)]">
                      <p>
                        <span className="text-[var(--text-muted)]">Requested by</span>{" "}
                        {bundle.context.requested_by} · {bundle.context.requested_via}
                      </p>
                      <p>
                        <span className="text-[var(--text-muted)]">Created</span>{" "}
                        {new Date(bundle.context.created_at).toLocaleString()} · age{" "}
                        {formatAgeSeconds(bundle.context.age_seconds)}
                      </p>
                      {bundle.context.mission_title ? (
                        <p>
                          <span className="text-[var(--text-muted)]">Mission</span>{" "}
                          {bundle.context.mission_link ? (
                            <Link
                              to={bundle.context.mission_link}
                              className="font-medium text-[var(--accent-blue)] hover:underline"
                            >
                              {bundle.context.mission_title}
                            </Link>
                          ) : (
                            bundle.context.mission_title
                          )}
                          {bundle.context.mission_status ? (
                            <span className="text-[var(--text-muted)]">
                              {" "}
                              ({bundle.context.mission_status})
                            </span>
                          ) : null}
                        </p>
                      ) : null}
                    </div>
                  </section>
                ) : null}

                {pk.operator_effect ? (
                  <section>
                    <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                      Operator effect
                    </h3>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">{pk.operator_effect}</p>
                  </section>
                ) : null}

                {pk.target_summary ? (
                  <section>
                    <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                      Target
                    </h3>
                    <p className="mt-1 font-mono text-xs text-[var(--text-primary)]">{pk.target_summary}</p>
                  </section>
                ) : null}

                {pk.preflight_summary || pk.preflight_available ? (
                  <section>
                    <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                      Preflight
                    </h3>
                    {pk.preflight_summary ? (
                      <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">
                        {pk.preflight_summary}
                      </p>
                    ) : (
                      <p className="mt-1 text-xs text-[var(--text-muted)]">
                        No preflight snapshot on this mission timeline for this approval.
                      </p>
                    )}
                  </section>
                ) : null}

                {pk.fields.length > 0 ? (
                  <section>
                    <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                      Fields
                    </h3>
                    <dl className="mt-2 divide-y divide-[var(--bg-border)] rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)]/40">
                      {pk.fields.map((row) => (
                        <div key={row.label} className="grid gap-0.5 px-3 py-2 md:grid-cols-[minmax(0,11rem)_1fr]">
                          <dt className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                            {row.label}
                          </dt>
                          <dd className="break-words text-xs text-[var(--text-primary)]">{row.value}</dd>
                        </div>
                      ))}
                    </dl>
                  </section>
                ) : null}

                {pk.parse_note ? (
                  <p className="text-xs text-[var(--text-muted)]">{pk.parse_note}</p>
                ) : null}

                {bundle?.notes?.length ? (
                  <ul className="list-inside list-disc text-xs text-[var(--text-muted)]">
                    {bundle.notes.map((n) => (
                      <li key={n}>{n}</li>
                    ))}
                  </ul>
                ) : null}

                {bundle?.recent_events?.length ? (
                  <details className="group">
                    <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                      Recent mission events ({bundle.recent_events.length})
                    </summary>
                    <ul className="mt-2 space-y-1 font-mono text-[10px] text-[var(--text-muted)]">
                      {bundle.recent_events.map((ev) => (
                        <li key={ev.id}>
                          {ev.event_type} — {ev.summary || "—"}
                        </li>
                      ))}
                    </ul>
                  </details>
                ) : null}

                {bundle?.related_receipts?.length ? (
                  <details className="group">
                    <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                      Related receipts ({bundle.related_receipts.length})
                    </summary>
                    <ul className="mt-2 space-y-1 font-mono text-[10px] text-[var(--text-muted)]">
                      {bundle.related_receipts.map((r) => (
                        <li key={r.id}>
                          {r.receipt_type} — {r.summary ?? "—"}
                        </li>
                      ))}
                    </ul>
                  </details>
                ) : null}

                {bundle?.data_quality ? (
                  <details className="group border-t border-[var(--bg-border)] pt-3">
                    <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                      Data quality
                    </summary>
                    <div className="mt-2 space-y-2 text-[10px] text-[var(--text-muted)]">
                      <p className="font-medium text-[var(--text-secondary)]">Direct from store</p>
                      <ul className="list-inside list-disc">
                        {bundle.data_quality.direct_from_store.map((x) => (
                          <li key={x}>{x}</li>
                        ))}
                      </ul>
                      <p className="font-medium text-[var(--text-secondary)]">Derived</p>
                      <ul className="list-inside list-disc">
                        {bundle.data_quality.derived.map((x) => (
                          <li key={x}>{x}</li>
                        ))}
                      </ul>
                    </div>
                  </details>
                ) : null}
              </div>
            ) : (
              <p className="text-sm text-[var(--text-muted)]">No packet data.</p>
            )}
          </>
        )}
      </div>

      <div className="shrink-0 border-t border-[var(--bg-border)] px-4 py-3 md:px-5">
        {showRaceSuccess ? (
          <div className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)]/80 px-3 py-2.5">
            <p className="text-xs font-medium text-[var(--text-secondary)]" role="status">
              {approvalPostDecisionLine(recentlyResolvedDecision!)}
            </p>
            <p className="mt-1 text-[10px] text-[var(--text-muted)]">{operatorCopy.approvalRefreshingState}</p>
          </div>
        ) : showPendingButtons ? (
          <div className="flex flex-col gap-2">
            {resolving ? (
              <p className="text-xs text-[var(--text-muted)]" role="status" aria-live="polite">
                {operatorCopy.approvalRecording}
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={resolving}
                aria-disabled={resolving === true}
                onClick={() => void onApprove()}
                className="min-h-[40px] min-w-[120px] rounded-lg border border-emerald-500/35 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200/95 transition-colors hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Approve
              </button>
              <button
                type="button"
                disabled={resolving}
                aria-disabled={resolving === true}
                onClick={() => void onDeny()}
                className="min-h-[40px] min-w-[120px] rounded-lg border border-[var(--bg-border)] bg-transparent px-4 py-2 text-sm font-semibold text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)]/60 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Deny
              </button>
            </div>
            {resolveError ? (
              <p className="text-xs text-[var(--status-red)]">{operatorCopy.approvalResolveFailed}</p>
            ) : null}
          </div>
        ) : (
          <p className="text-center text-xs font-medium text-[var(--text-secondary)]">
            {approval.status === "approved"
              ? "Approved"
              : approval.status === "denied"
                ? "Denied"
                : approval.status}
            {approval.decided_at ? (
              <span className="mt-1 block font-mono text-[10px] font-normal text-[var(--text-muted)]">
                {new Date(approval.decided_at).toLocaleString()}
              </span>
            ) : null}
          </p>
        )}
      </div>
    </div>
  );
}
