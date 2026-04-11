# Mission timing and runtime health (Command Center)

This document describes the **lightweight, event-derived** timing shown on the mission detail page and how to interpret delays. There is no separate analytics pipeline; numbers come from persisted mission events and the mission row’s `updated_at`.

## Operator phase line (mission detail, readouts, cards)

The Command Center shows a **single short phase line** (e.g. under the mission title on detail, and as the first line on mission cards / right-panel readout when space is tight). This is a **derived UI readout**, not a new backend field or a second source of truth.

**Inputs** (same as the rest of the UI): `mission.status`, timeline `mission_events`, pending/approved rows from the approvals list, and receipt rows / `receipt_recorded` events.


| Phase (code)                    | Typical label                           | Meaning                                                                                                                                                                     |
| ------------------------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `awaiting_approval`             | Awaiting approval                       | Status or approvals indicate governance is still open.                                                                                                                      |
| `resumed_waiting_for_execution` | Approved - waiting for execution output | `approval_resolved` (approve) is on the timeline, mission is **active**, and there is **no** execution evidence yet.                                                        |
| `executing`                     | Executing                               | Active or pending **without** receipt evidence yet and not in the post-approval-waiting state above (e.g. warming up or no approval path).                                  |
| `execution_evidence_received`   | Execution updated                       | At least one receipt or `receipt_recorded` event exists; mission is **not** in a terminal **complete** state — evidence is present but the run is not necessarily finished. |
| `complete`                      | Complete                                | Mission status is **complete** (authoritative terminal success).                                                                                                            |
| `failed`                        | Failed                                  | Mission status is **failed**.                                                                                                                                               |
| `blocked`                       | Blocked                                 | Mission status is **blocked**.                                                                                                                                              |


**Important:** **Active** with receipts does **not** imply **Complete**. The phase stays **Execution updated** until the control plane marks the mission **complete**. Timing strips and the runtime health row use the same underlying events; they are complementary, not redundant authorities.

Implementation: `services/command-center/src/lib/missionPhase.ts` (`deriveOperatorMissionPhase`), wired through `deriveExecutiveMissionSummary` so detail, right panel, and cards stay aligned.

### Latest execution result (compact summaries)

The Command Center may show a **short “latest execution output / result” line** (overview triage, mission detail header, right rail) built by `deriveLatestExecutionResult` in `services/command-center/src/lib/missionLatestResult.ts`. It considers only **existing receipt rows** and **`receipt_recorded` timeline events** (newest `created_at` wins; tie-break prefers the receipt row). Headings distinguish **active** missions with evidence from **complete** vs **failed** terminal states — they do **not** replace mission status or phase; “Complete” / “Failed” remain the mission row + `deriveOperatorMissionPhase`. This is **presentation-only** over the same data the receipts section and timeline use, not a new source of truth. The conversation thread still surfaces execution text primarily via **receipt bubbles** in the transcript; the compact line is for scanability where a dense readout helps.

The **Missions** page (`MissionCard`) reuses the same **`LatestExecutionResultLine`** when **`shouldShowMissionListLatestPreview`** (in `missionLatestResult.ts`) is true: there is execution evidence on the timeline (`receipt_recorded` / receipts path consistent with `hasExecutionEvidence`), and the derived phase is not `awaiting_approval`, `resumed_waiting_for_execution`, or `executing` (those stay clean until evidence exists). Terminal **complete** / **failed** snapshots use a slightly lighter divider so settled rows do not overpower active-with-evidence cards. **Sorting and tab filters are unchanged** — this is presentation-only.

**Latest-result deep links:** `missionDetailLatestResultHref` / `missionDetailLatestResultHash` append `#receipts` or `#receipt-<id>` (`receiptAnchorDomId` / `MISSION_DETAIL_RECEIPTS_SECTION_ID`), matching stable DOM ids on mission detail. When **`sourceReceiptId`** is set on **`LatestExecutionResult`**, navigation targets that receipt row; otherwise the receipts section top. Overview recently-updated rows, Missions cards, and the right rail use the same helper so handoffs stay aligned — **navigation/presentation only**, not a new receipt authority.

### Mission detail receipts (progressive disclosure)

On **mission detail**, the **Receipts** section orders rows **newest first** and uses the same bundle/API receipt objects as everywhere else. The **newest receipt** is shown as an executive-first card (full summary, `execution_meta` line, inspectable JSON payload behind a disclosure). **Older receipts** render as **collapsed** `<details>` rows by default so the page does not become a log wall; expanding a row reveals the same fields. `deriveLatestExecutionResult` exposes optional **`sourceReceiptId`** when the newest evidence edge is a receipt row, so the highlighted primary card can stay aligned with the header “latest result” line without inventing data. This remains **presentation-only** over persisted receipts — not a new backend authority.

### Overview and mission list ordering

The **Overview** triage panel groups missions into **Needs attention**, **Running**, and **Recently updated** using `deriveOperatorMissionPhase` (same inputs as everywhere else). **Needs attention** includes `awaiting_approval` and `resumed_waiting_for_execution`; **Running** is `executing`; **Recently updated** is `execution_evidence_received`. Terminal phases (`complete`, `failed`, `blocked`) are listed separately in a compact **Settled** section so they do not crowd out active work. Within each bucket, ordering still uses `sortMissionsForOperatorListing` (staleness-first for non-terminal phases). The **Missions** page list uses the same sort over the full filtered set.

All of this is **presentation-only** logic in `missionListPriority.ts` — it does **not** change backend ordering, SSE payloads, or hydration; it is **not** a new source of truth. Staleness hints (e.g. a short “Queue” line on cards) are derived from the same inputs and are meant to help triage, not to imply a mission is broken.

**Overview handoff:** Triage rows are **navigation controls**: they link to `/missions/:id` and call the shell’s existing `setThreadMissionId` so the conversation thread and right panel align with the opened mission (the same anchor `MissionDetail` sets on load). Section **View all** links use the `triage` query parameter (`?triage=needs_attention` etc.) to open the missions list with the same derived bucket filter — still presentation/navigation only, not new mission authority.

**Overview freshness (optional cues):** The triage panel may show **lightweight text cues** (e.g. “New”, “Just updated”, “Needs review”) and a **· N new** count on section headers when recent mission/event timestamps fall within a short UI window (`OVERVIEW_FRESHNESS_WINDOW_MS` in `missionListPriority.ts`). The **Recently updated** overview bucket also **drops** missions whose last execution evidence is older than `OVERVIEW_RECENTLY_UPDATED_MAX_EVIDENCE_AGE_MS` so the overview stays triage-oriented; the full missions list and other surfaces are unchanged. This is **presentation-only guidance** from existing timestamps — not alerts, not persisted state, and not a second source of truth.

**Needs attention (approval handoff):** In the **Needs attention** bucket, rows may show a **compact approval preview** (action type, risk class, short reason) from the same **pending approvals** list already loaded for the app, plus a **Review** link to the mission route with the same shell `threadMissionId` handoff as the main row. When there is **exactly one** pending approval with full metadata, small **Approve** / **Deny** controls may call the same resolve API used elsewhere; they do **not** introduce a new approval authority or persisted UI state beyond existing patterns. After a successful decision, the UI may show a **brief confirmation** (shared with other surfaces) while lists refresh — still **presentation-only**; the operator phase line continues to come from derived mission/events data once updated. This remains **presentation and navigation over existing mission/governance truth**.

## What each timing means


| Label                              | Definition                                                                                                                                                                                    |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Time to approval request**       | Wall time from mission creation (or the `created` event timestamp, if present) until the first `approval_requested` event.                                                                    |
| **Governance window**              | Time from `approval_requested` to `approval_resolved` (operator decision recorded in the timeline).                                                                                           |
| **Time to first execution result** | If there was an approval path: time from `approval_resolved` to the first `receipt_recorded` event. If there was no approval request: time from creation (or `created`) to the first receipt. |
| **Last updated**                   | Mission row `updated_at` — relative time shown in the UI (same as elsewhere in the app).                                                                                                      |


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

