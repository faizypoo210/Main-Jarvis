# Failure modes — Jarvis mission loop

This document describes how the **control plane** (authoritative state), **SSE live stream**, and **command center** behave under unhappy-path conditions, and what operators should expect.

## Design constraints (unchanged)

- Single source of truth: control plane API + persisted `mission_events`.
- Command center does **not** invent mission state; it deduplicates and merges server data.
- **Mission phase** lines (Awaiting approval, Executing, Execution updated, etc.) are **derived in the UI** from the same mission row + events + receipts — not a parallel backend status. See [MISSION_TIMING.md](./MISSION_TIMING.md#operator-phase-line-mission-detail-readouts-cards). The same `deriveOperatorMissionPhase` helper drives mission detail, executive readout, **conversation thread** status lines, **voice overlay** mission line, and timeline empty-state hints so wording stays aligned.
- No “fake optimistic” mission completion — only **approval cards** reflect an immediate client update after a successful `POST …/decision`, aligned with the API response.

## What is covered in code

| Area | Behavior |
|------|----------|
| **SSE duplicate events** | `appendEvent` ignores the same `event.id` twice. Timeline and shared state stay single-sourced. |
| **Bundle vs live merge** | `hydrateMissionBundle` **merges** events by id with existing SSE-backed events instead of replacing the list (avoids losing rows during reconnect / refetch races). |
| **Thread duplicate bubbles** | `receipt_recorded` execution bubbles keyed by `exec-${event.id}`; replays do not add a second bubble. |
| **Approval resolved targeting** | `approval_resolved` updates only the approval card matching `payload.approval_id` when present. |
| **Mission failed line** | Single stable id `status-fail-${missionId}` — no `Date.now()` duplicate rows. |
| **Empty receipt summary** | Backend always emits `summary` on `receipt_recorded` payload (string, possibly empty). UI uses calm copy for empty vs failed mission. |
| **Approval event payload** | `approval_resolved` includes `decided_at` (ISO), `decided_via`, consistent with approvals API. |
| **Status writes** | `MissionRepository.update_status` skips `mission_status_changed` when status is unchanged (no noise). |
| **Degraded copy** | Centralized in `services/command-center/src/lib/operatorCopy.ts` (reconnecting, offline polling, partial bundle, empty receipt). |
| **Approval POST failures** | Shared `useResolveApprovalAction` hook: one mutation path, duplicate-submit guard while a decision is in flight, quiet `operatorCopy.approvalResolveFailed`, then `refetchPendingApprovals` + `refetchMissions`. Overview, thread, right panel, mission detail, approvals inbox, and voice overlay all use this path; mission detail and voice may pass `onSuccess` for bundle/thread-specific refresh. Still one control-plane approval authority — not parallel client semantics. |
| **Post-decision UI (presentation-only)** | After a **successful** `POST …/decision`, the hook exposes a short-lived `lastResolved` + `recentlyResolvedDecisionFor(approvalId)` so surfaces can show calm confirmation (via `approvalPresentation` + `operatorCopy`) while the pending list refetches — **not** a second source of truth; derived mission phase lines still come from refreshed mission/events as before. |
| **Latest execution result line** | `deriveLatestExecutionResult` merges receipt rows + `receipt_recorded` events for a compact “latest output” hint; wording stays consistent via `operatorCopy` and does not override mission terminal status. Optional `sourceReceiptId` links the hint to a receipt row when applicable. |
| **Receipt list layout** | Mission detail receipts use `receiptPresentation` helpers: newest card first, older rows collapsed by default; full payload JSON stays behind disclosure. |
| **Missions list preview** | `MissionCard` may show `LatestExecutionResultLine` when `shouldShowMissionListLatestPreview` passes — same receipt/event derivation as elsewhere; no change to list sort or filters. |
| **Latest-result hash handoff** | `missionDetailLatestResultHref` links to `#receipts` or `#receipt-<id>` on mission detail; DOM ids match bundle receipt rows / section anchor only. |
| **Diagnostics** | Mission detail, conversation thread, and right panel show short stream/polling hints when not `live`. |

## Simulated vs natural

| Scenario | How we verify |
|----------|----------------|
| **Health + API shape** | `scripts/12-test-failure-modes.ps1` — GET `/health`, missions list, optional bundle/events uniqueness. |
| **Duplicate event IDs** | Script asserts mission event lists from API have **unique** `id` values (DB invariant). Client dedupe is verified by code review + UI behavior. |
| **SSE disconnect/reconnect** | **Natural** during runtime (or kill/restart control plane). Operator sees “Live updates reconnecting.” / offline polling copy. |
| **Duplicate SSE delivery** | **Natural** if broker replays; client `appendEvent` dedupes. |
| **approval_requested before hydration** | **Natural**; thread builds approval from event payload when pending list is empty. |
| **Double resolve** | **Natural** only via API test; server returns **400** if not pending — no extra mission event. |
| **Executor / gateway failure** | **Natural** when worker posts failed status/receipts; UI shows mission failed copy and empty-receipt messaging when appropriate. |
| **Bundle temporarily unavailable** | **Natural** if network blips; detail page shows partial banner when bundle load fails but mission exists from list. |

## Single-process / SSE assumptions

- The **browser** holds one SSE connection to `/api/v1/updates/stream` per Command Center tab.
- **Reconnect** uses exponential backoff in the client; between reconnects, **polling** (`bootstrapMission`, pending approvals) still runs when the stream is down.
- **Multi-tab**: each tab has its own stream; state merges from the same API — duplicates are still suppressed by `event.id`.
- **Horizontal scale**: if multiple control plane instances shared one DB but separate in-memory hubs, SSE routing could differ — not part of the current deployment model.

## Operator-visible cues (by situation)

| Situation | What you should see |
|-----------|----------------------|
| Stream reconnecting | “Live updates reconnecting.” (thread, detail, right panel as applicable) |
| Stream offline | “Live stream offline — using periodic sync.” |
| Bundle error but mission known | “Mission state updated. Detailed output unavailable.” |
| Awaiting approval but list not yet synced | “Approval pending — refreshing approvals.” |
| Receipt with no summary, mission failed | “Execution failed before a receipt summary was available.” |
| Receipt with no summary, not failed | “Receipt recorded without a summary.” |
| Mission failed, no receipt detail in thread | “Mission failed before detailed output arrived.” |

## Remaining weakest edges

1. **Ordering vs clock skew** — Events sort by `created_at` then `id`; extreme clock skew across writers could theoretically mis-order; operations assume monotonic DB timestamps.
2. **Cross-mission noise in thread** — Only **watched** `missionId`s are processed; unrelated missions do not inject items (by design). If that set were wrong, pollution could occur — guarded by `watchedMissionIdsRef`.
3. **Double approval resolve from UI** — Rapid double-submit could hit 400 on the second call; card may already show resolved — operator may see a transient error on the card until refresh.

## Related files

- Client: `ControlPlaneLiveContext.tsx` (merge + dedupe), `useResolveApprovalAction.ts`, `ConversationThread.tsx`, `MissionTimeline.tsx`, `MissionDetail.tsx`, `operatorCopy.ts`
- Server: `mission_repo.py` (no-op status), `approval_service.py`, `receipt_service.py`, `mission_event_repo.py`
