# Mission timing and runtime health (Command Center)

This document describes the **lightweight, event-derived** timing shown on the mission detail page and how to interpret delays. There is no separate analytics pipeline; numbers come from persisted mission events and the mission row’s `updated_at`.

## What each timing means

| Label | Definition |
| ----- | ---------- |
| **Time to approval request** | Wall time from mission creation (or the `created` event timestamp, if present) until the first `approval_requested` event. |
| **Governance window** | Time from `approval_requested` to `approval_resolved` (operator decision recorded in the timeline). |
| **Time to first execution result** | If there was an approval path: time from `approval_resolved` to the first `receipt_recorded` event. If there was no approval request: time from creation (or `created`) to the first receipt. |
| **Last updated** | Mission row `updated_at` — relative time shown in the UI (same as elsewhere in the app). |

Receipts are the primary signal that execution produced something observable on the wire. The timeline is the source of truth for “first result.”

## Runtime health row

A single **Runtime** line (no dashboard) summarizes three coarse signals:

1. **Updates** — Whether the live channel is **Live**, **Reconnecting**, or **Polling** (fallback when SSE is not connected).
2. **Approvals** — **OK** when the pending-approvals fetch is healthy; **Degraded** if that request failed (you may still see approvals from the mission bundle).
3. **Execution** — **Receipt** when at least one receipt exists; **Awaiting** when the mission is still active/pending without receipts; **Paused** when status is awaiting approval; **Settled** when the mission reached a terminal status; **Degraded** if loading the mission bundle failed (timeline/receipts may be incomplete).

These are **interpretive hints**, not guarantees. They help you decide where to look next (network, governance API, executor) without exposing a full diagnostics wall.

## Interpreting abnormal delays

- **Long time to approval request** — Work may be queued before governance is invoked, or the agent may be slow to emit the request. Compare with your expected SLA for “human in the loop.”
- **Long governance window** — Operator time or UI; also check if approvals failed to load (`Approvals Degraded`).
- **Long time to first execution result after approval** — Executor backlog, tool failures, or missing receipt emission. If **Execution** stays **Awaiting** while status is active, the run may be stuck or receipts may not be persisted.
- **Reconnecting / Polling under Updates** — Live updates are impaired; you may see stale data until the stream recovers or polling refreshes. See [REALTIME_UPDATES.md](./REALTIME_UPDATES.md).

## Limitations (no backend change required for the UI)

- **Clock skew** — Different services may write `created_at` with slightly different clocks; rare negative or weird gaps are possible.
- **Missing events** — If a receipt exists in the API but the corresponding `receipt_recorded` event was never written, timing may show **—** until events align.
- **Approval path without** `approval_resolved` — If the timeline is incomplete, “Governance window” and “Time to first execution result” may be empty or fall back to coarser spans.
- **Terminal status** — Event-level `mission_status_changed` to complete/failed/blocked is tracked in the model for future use; the UI focuses on operator-facing durations above.

## Optional backend improvements (if you need tighter truth)

- Ensure every receipt is mirrored as a `receipt_recorded` event with a consistent timestamp.
- Emit `approval_requested` / `approval_resolved` in strict order with monotonic timestamps.
- If you need sub-second or cross-service latency, add a single server-side “mission timeline” aggregation endpoint — still avoid heavy analytics infra.
