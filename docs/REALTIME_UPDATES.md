# Real-time updates (control plane → Command Center)

This document describes how Jarvis surfaces **authoritative** mission and approval state with **low latency** and **no second source of truth**.

## Source of events

All live payloads are derived from the **same rows** the REST API already exposes:

- **Mission timeline:** `MissionEvent` rows, serialized as `MissionEventRead` (same shape as `GET /api/v1/missions/{id}/events`).
- **Mission snapshot:** `Mission` rows, serialized as `MissionRead` (same shape as `GET /api/v1/missions/{id}`).

When a transaction commits successfully, the control plane **queues** zero or more JSON messages (`session.info["realtime_emit"]`). After `commit`, those messages are broadcast to every connected **Server-Sent Events (SSE)** client on:

`GET /api/v1/updates/stream`

Authentication uses the same **`x-api-key`** header as other control-plane APIs. The Command Center uses **fetch + ReadableStream** (not `EventSource`) so the key can be sent in headers from browsers.

## Status transitions on the timeline

Whenever `MissionRepository.update_status` changes a mission’s status, a **`mission_status_changed`** event is written with payload `{ "from": "<previous>", "to": "<new>" }`. This makes chronology **trustworthy** without inferring lifecycle from `MissionRead` alone.

Other event types (`created`, `approval_requested`, `approval_resolved`, `receipt_recorded`) are unchanged and remain the single timeline source.

## Mission bundle (first paint)

`GET /api/v1/missions/{mission_id}/bundle` returns one JSON object:

- `mission` — `MissionRead`
- `events` — `MissionEventRead[]`
- `approvals` — `ApprovalRead[]`
- `receipts` — `ReceiptRead[]`

The mission detail route uses this for **one** hydration round-trip, then relies on SSE + targeted approval/receipt refresh (debounced) so the UI stays aligned without redundant full reloads on every global event.

## Enriched mission event payloads (existing)

| `event_type`          | Payload highlights |
|-----------------------|--------------------|
| `approval_requested`  | `approval_id`, `mission_id`, `action_type`, `risk_class`, `reason`, `status` |
| `approval_resolved`   | `approval_id`, `mission_id`, `decision`, `decided_by` |
| `receipt_recorded`    | `summary`, `execution_meta` (when present), plus receipt metadata |
| `mission_status_changed` | `from`, `to` (string statuses) |

## Hydration + subscription flow (Command Center)

1. **`ControlPlaneLiveProvider`** performs an initial **hydration** fetch:
   - `GET /api/v1/missions?limit=500`
   - `GET /api/v1/approvals/pending`
2. It maintains a **single** SSE subscription with **automatic reconnect** (see below).
3. Incoming messages merge into shared state:
   - `type: mission_event` → append to `eventsByMissionId` (deduped by event `id`).
   - `type: mission` → upsert `missionById` and the missions list.
4. On `approval_requested`, `approval_resolved`, or `mission_status_changed`, pending approvals are **refetched** once (no optimistic fake approvals).

`bootstrapMission()` prefers **`getMissionBundle`** and falls back to separate mission + events GETs if the bundle fails.

## SSE reconnect behavior

- On HTTP failure, stream EOF, or read error, the client sets **`streamPhase`** to `offline`, records **`streamError`**, and schedules a reconnect with **exponential backoff** (base 1s, ceiling 30s).
- While waiting or actively reconnecting, **`streamPhase`** is `reconnecting`.
- After a successful HTTP response (`onOpen`), **`streamPhase`** becomes **`live`** until the next failure or disconnect.
- Only **one** subscription exists at a time; cleanup **aborts** the previous `fetch` before starting a new attempt, avoiding duplicate readers.
- Event application remains **idempotent** (dedupe by mission event id).

## Fallback polling behavior

When **`streamPhase !== 'live'`** (i.e. not connected):

- `useMissions` / `usePendingApprovals` / `usePolledMissionDetail` / `useMission` use their existing **interval** refetch paths so lists and focused missions stay **eventually** consistent.

This is **not** a second authority: the same REST endpoints and rows back both SSE snapshots and polling.

## UI: live health

The shell shows a compact **Live / Reconnecting / Offline** indicator (desktop left rail) derived from **`streamPhase`**. Voice overlay mirrors the same phases with restrained copy.

## Why this is not a second authority

- No parallel event bus: only **queued snapshots** of ORM rows already written for REST.
- No optimistic governance: approvals still resolve through **`POST /api/v1/approvals/{id}/decision`**; the stream only **reflects** outcomes.

## Operational notes

- SSE is **in-process** (single control-plane instance). Horizontal scale would require a shared pub/sub (e.g. Redis) **without** changing the canonical DB model; the enqueue point would move from `session.info` to a shared channel after commit.
