# Golden path — operator rehearsal

This is the **canonical end-to-end loop** the Command Center is built around: command → mission → governance → approve → execution evidence → inspectable truth in mission detail.

For the **full runtime chain** (Redis → coordinator / DashClaw → executor / OpenClaw) without synthetic `POST /approvals` or `POST /receipts`, see [`LIVE_STACK_REHEARSAL.md`](./LIVE_STACK_REHEARSAL.md) and `scripts/14-rehearse-live-stack.ps1`.

## Automated rehearsal (API truth)

Run from the repo root (control plane must be up; Postgres reachable):

```powershell
$env:CONTROL_PLANE_API_KEY = '<your key>'   # if auth enabled
.\scripts\13-rehearse-golden-path.ps1
# Optional: .\scripts\13-rehearse-golden-path.ps1 -ControlPlaneUrl http://localhost:8001
```

The script uses **only control plane HTTP APIs** (same surfaces as the product):

1. `POST /api/v1/commands` — create mission  
2. `POST /api/v1/approvals` — request approval (same path a coordinator uses)  
3. `GET /api/v1/approvals/pending` — confirm pending row  
4. `POST /api/v1/approvals/{id}/decision` — approve  
5. `GET /api/v1/missions/{id}` — mission active after approval  
6. `POST /api/v1/receipts` — record receipt (same path executors use)  
7. `GET /api/v1/missions/{id}/bundle` — verify events, approvals, receipts  

It does **not** bypass governance, invent status, or use a second source of truth.

### Isolation from Redis / runtime execution

`13-rehearse-golden-path.ps1` sends an explicit command **context** so the control plane **does not publish** to `jarvis.commands` for that mission:

- `context.rehearsal_mode = "synthetic_api_only"`
- `context.skip_runtime_publish = true`

Mission rows and `created` events behave as usual; only the Redis fan-out is skipped so a **full live stack** (coordinator + executor) on the same machine does not pick up synthetic missions and collide with this rehearsal. Normal Command Center traffic does not send these markers.

For **timed benchmarks**, JSON reports under `docs/reports/`, and the baseline workflow with `14` and `15`, see [`OPERATOR_EVALS.md`](./OPERATOR_EVALS.md) and `scripts/15-benchmark-operator-loop.ps1`. To run **semantics + this golden path + optional synthetic-only benchmark** in one command, use `scripts/17-verify-operator-evals.ps1` (see **Recommended quick check** in [`OPERATOR_EVALS.md`](./OPERATOR_EVALS.md)).

## What you should see in the UI (Faiz)

Assume Command Center is open with live SSE or fallback polling. After the script completes, open **`/missions/{mission_id}`** (the script prints the id). Replace “within a few seconds” with your tolerance for SSE + polling.

### Thread (Overview)

| Phase | Expected |
|--------|----------|
| After command (if you had issued the same text in-app) | User line + “Understood…” + mission pipeline activity; approval card appears when governance is required. |
| After script stages B–C | If you were watching another mission, you may **not** see this mission’s thread — thread follows **shell focus**. Navigate to mission detail or set focus by opening the mission. |
| Rehearsal via script only | Thread may not update until you open the mission or refresh list — **mission detail is the audit surface**. |

### Voice overlay

| Phase | Expected |
|--------|----------|
| Pending approval on **focused** mission | Governance orb/title, one-line “Decision required…”, **Voice approval brief** (action, risk, reason), View / Approve / Deny. |
| Pending only elsewhere | Short amber line: approvals pending on other missions. |
| After approve, mission active | Lines progress: “Awaiting execution output.” → “Execution updated.” once a receipt exists (timeline order). |
| Stream offline | Calm copy: live stream offline — periodic sync (no alarmist styling). |

### Right panel

| Phase | Expected |
|--------|----------|
| Focused mission matches shell | Title, status badge, stage line if present, **Mission readout** from live events + pending list. |
| Pending on this mission | Pending approval cards; count badge. |
| After approval | Pending count drops; “No pending approvals” when none left; recent activity lists event types. |

### Mission detail (canonical truth)

Use this page to confirm the rehearsal: **Timeline**, **Approvals**, **Receipts** should align with bundle.

| Check | Healthy |
|--------|---------|
| Timeline order | `created` → `approval_requested` → `approval_resolved` → `receipt_recorded` (ordering by time + id). |
| Approvals | One row **approved** with decided metadata. |
| Receipts | At least one receipt; summary text present; **Execution** line under receipt when `execution_meta` was posted. |
| Status | **Active** after approve; receipt does not by itself flip to complete unless something else updates status. |

## Timing and “slightly delayed” is OK

| Effect | Healthy behavior |
|--------|------------------|
| SSE reconnect | Brief “Live updates reconnecting.” — lists refill on next poll or reconnect. |
| Approval list lag | Pending may appear in mission detail or thread a moment after `approval_requested` event — refetch clears it. |
| Executor not in loop | This rehearsal **posts the receipt via API**; a real stack would have the executor POST the same endpoint. Delay until receipt is normal in live runs. |
| Bundle vs thread | Thread dedupes by event id; bundle is authoritative for “what happened.” If unsure, **refresh mission detail**. |

## Unhealthy (investigate)

- Mission stuck in `awaiting_approval` after a successful approve POST.  
- Duplicate timeline rows for the **same** event id (should not happen after dedupe).  
- Bundle missing events that `/missions/{id}/events` shows (should not diverge — report as bug).  

## Full stack vs API-only rehearsal

- **API-only script**: Proves control plane contracts and persistence; UI checklist above is what you validate manually (or with browser open on the printed mission id).  
- **Full stack**: Coordinator + executor can drive the same phases without manual receipt POST; timing is looser, but mission detail should still match the same event types when things are healthy.

## Deferred (not part of this doc)

- Spoken approve/deny through voice WebSocket.  
- Automated browser/UI assertion (Playwright, etc.) — optional future work.
