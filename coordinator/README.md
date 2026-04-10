# JARVIS Event Coordinator

Async Python service that connects **Redis Streams**, **DashClaw** (governance), and the **Jarvis Control Plane** (mission state). It reads voice/UI commands and OpenClaw receipts from streams, calls DashClaw **guard** and **outcomes** endpoints, and publishes execution work and UI updates back to Redis.

## Flow

1. **Commands** (`jarvis.commands`): insert or ensure a mission row (`pending`), POST DashClaw `/api/guard`, then:
   - `allow` → `active`, message to `jarvis.execution`
   - `requires_approval` → `awaiting_approval`, approval payload to `jarvis.updates`
   - `deny` → `failed` (guard denied)
2. **Receipts** (`jarvis.receipts`): POST DashClaw `/api/outcomes`, set mission `complete` or `failed`, summary to `jarvis.updates`.

## State

The coordinator is stateless. All mission state lives in the
Jarvis Control Plane (PostgreSQL via FastAPI at CONTROL_PLANE_URL).
The coordinator reads Redis streams, calls DashClaw for policy
evaluation, and POSTs state changes back to the control plane.
No local database is used.

## Redis Streams

| Stream | Direction |
|--------|-----------|
| `jarvis.commands` | Read (consumer group `jarvis-coordinator-commands`) |
| `jarvis.execution` | Write |
| `jarvis.receipts` | Read (consumer group `jarvis-coordinator-receipts`) |
| `jarvis.updates` | Write |

Messages use a `data` field containing JSON.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `REDIS_URL` | Redis URL (default `redis://localhost:6379`) |
| `CONTROL_PLANE_URL` | Control plane base URL (default `http://localhost:8001`) |
| `DASHCLAW_BASE_URL` | DashClaw base URL (no trailing slash required) |
| `DASHCLAW_API_KEY` | DashClaw API key (sent as `Authorization: Bearer …`) |
| `JARVIS_OPERATOR` | Optional default for mission `created_by` when not in the command payload |

Set secrets in Windows User environment variables; do not commit them.

## Setup

```powershell
cd F:\Jarvis\coordinator
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

Start from the repo (after configuring env vars):

```powershell
F:\Jarvis\scripts\09-start-coordinator.ps1
```

## Logs

Each processed event logs one JSON line: `timestamp`, `stream`, `event_type`, `mission_id`, `decision`.
