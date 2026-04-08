# JARVIS Event Coordinator

Async Python service that connects **Redis Streams**, a **local SQLite** mission store (`missions.db`), and **DashClaw** (governance). It reads voice/UI commands and OpenClaw receipts from streams, records missions in SQLite, calls DashClaw **guard** and **outcomes** endpoints, and publishes execution work and UI updates back to Redis.

## Flow

1. **Commands** (`jarvis.commands`): insert or ensure a mission row (`pending`), POST DashClaw `/api/guard`, then:
   - `allow` → `active`, message to `jarvis.execution`
   - `requires_approval` → `awaiting_approval`, approval payload to `jarvis.updates`
   - `deny` → `failed` (guard denied)
2. **Receipts** (`jarvis.receipts`): POST DashClaw `/api/outcomes`, set mission `complete` or `failed`, summary to `jarvis.updates`.

## SQLite: `missions.db`

Default path: **`F:\Jarvis\coordinator\missions.db`** (same directory as `coordinator.py`). The `missions` table:

| Column | Purpose |
|--------|---------|
| `id` | Primary key (UUID string) |
| `title` | Short label derived from the command |
| `status` | `pending` \| `active` \| `awaiting_approval` \| `complete` \| `failed` |
| `created_by` | From command JSON `created_by`, or `JARVIS_OPERATOR` env, or empty |
| `decision` | Last guard/outcome decision string when set |
| `risk_level` | From DashClaw guard when present |
| `created_at` / `updated_at` | ISO-8601 timestamps (UTC) |

The database file is created on first run.

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
