# Live-stack rehearsal

This document describes **`scripts/14-rehearse-live-stack.ps1`**, which validates the **real operational chain** through Redis, the coordinator (DashClaw guard), the executor (OpenClaw), and the control plane — **without** manually creating approvals or receipts.

## How this differs from the synthetic golden path

| | **Synthetic** [`13-rehearse-golden-path.ps1`](./GOLDEN_PATH.md) | **Live stack** `14-rehearse-live-stack.ps1` |
|---|----------------------------------|--------------------------------|
| Approval | `POST /api/v1/approvals` (direct API) | Waits for **pending approval created by coordinator** after DashClaw `requires_approval` |
| Receipt | `POST /api/v1/receipts` (direct API) | Waits for **`receipt_recorded` from executor** (OpenClaw → control plane) |
| Proof | Control plane contracts + DB | **End-to-end runtime** behavior |

Both scripts are kept: synthetic is fast and environment-light; live-stack proves the **wiring** operators rely on in production.

## What is proven when `LIVE_STACK_PASS` prints

1. **Control plane** — `/health` OK; commands and approvals use real HTTP + API key.
2. **Redis** — PING OK; **consumer groups** exist on `jarvis.commands` (`jarvis-coordinator-commands`) and `jarvis.execution` (`jarvis-executor`), indicating coordinator and executor have started and registered.
3. **Command path** — `POST /commands` creates a mission and publishes to Redis (control plane side).
4. **Coordinator / DashClaw** — A **pending approval** appears for the mission without manual `POST /approvals` (guard outcome → `request_approval` path).
5. **Approval resolution** — `POST …/decision` approve (same as Command Center).
6. **Executor / OpenClaw** — A **`receipt_recorded` event** with **non-empty summary** appears (executor posts receipts to the control plane).
7. **Bundle** — `GET …/bundle` shows `created`, `approval_requested`, `approval_resolved`, `receipt_recorded`, plus approval and receipt rows.

## Healthy timing

- **First-time stack**: After coordinator/executor start, streams and groups exist; first command may take **several seconds** to show a pending approval (DashClaw HTTP + DB).
- **After approve**: Resume publishes to `jarvis.execution`; executor + OpenClaw may take **tens of seconds to a few minutes** depending on model and gateway load.
- **SSE / Command Center**: The UI may lag the API by **one poll or reconnect**; mission detail after success is authoritative.

## Failure stages (`LIVE_STACK_FAIL stage=…`)

| Stage | Usually means |
|-------|----------------|
| `CP` | Control plane down or wrong URL / no API key. |
| `REDIS` | Redis not running, wrong container name, or coordinator/executor not started (no consumer groups on streams). |
| `CMD` | Command POST rejected (auth, validation). |
| `GUARD` | Coordinator not consuming, DashClaw unreachable/misconfigured, or command text **allowed** by guard (receipt appears early — script fails by design). |
| `APRV` | Decision POST failed (network, approval already resolved). |
| `EXEC` | Executor not running, OpenClaw failing, or execution not reaching receipt POST. |
| `BUNDLE` | Data inconsistency after events (rare); re-fetch or inspect DB. |

## Prerequisites

- `CONTROL_PLANE_API_KEY` set (when auth enabled).
- Docker Redis container `jarvis-redis` (or set `redis-cli` on PATH and adjust script if needed).
- **Coordinator** and **executor** processes running with correct `REDIS_URL`, `CONTROL_PLANE_URL`, `DASHCLAW_*`, OpenClaw gateway reachable from executor.
- Default approval command text is chosen to **typically** require approval under your DashClaw policy; override with `-ApprovalCommandText` or `JARVIS_SMOKE_APPROVAL_COMMAND` if your guard differs.

## Run

```powershell
$env:CONTROL_PLANE_API_KEY = '<key>'
.\scripts\14-rehearse-live-stack.ps1
# Optional: -ControlPlaneUrl http://localhost:8001 -PollTimeoutSec 400
```

Exit code **0** only on full pass; **non-zero** with `LIVE_STACK_FAIL stage=…` for targeted diagnosis.

To capture **wall-clock and event-derived timings** alongside this rehearsal, use [`OPERATOR_EVALS.md`](./OPERATOR_EVALS.md) and `scripts/15-benchmark-operator-loop.ps1 -IncludeLiveStack`.
