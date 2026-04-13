# Jarvis Control Plane

Authoritative backend for missions, timeline events, approvals, receipts, workers, integrations, cost tracking, and surface sessions. Surfaces (voice, web UI, SMS, API) call this service; OpenClaw is the execution plane and reports here.

## Setup

1. Copy `.env.example` to `.env` and set `DATABASE_URL`, `SECRET_KEY`, and other values for your environment.
2. Create a virtual environment and install dependencies:

   ```powershell
   cd F:\Jarvis\services\control-plane
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```

3. Ensure PostgreSQL is running and the target database exists. Apply migrations:

   ```powershell
   $env:PYTHONPATH = "$PWD"
   .\.venv\Scripts\alembic upgrade head
   ```

4. Run the API (default port **8001** in this repo to avoid clashing with the voice server on 8000):

   ```powershell
   $env:PYTHONPATH = "$PWD"
   .\.venv\Scripts\uvicorn app.main:app --reload --port 8001
   ```

## Key endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| POST | `/api/v1/intake` | **Unified intake** — interpret text, then mission / approval / inbox / status / reply-only (see `app/schemas/intake.py`) |
| POST | `/api/v1/commands` | **Primitive** command → mission + `mission_events` row (no interpretation; use when callers already classified intent) |
| GET | `/api/v1/missions` | List missions (filters: `status`, `created_by`, `limit`, `offset`) |
| GET | `/api/v1/missions/{id}` | Single mission |
| — | `/api/v1/missions/{id}/events`, `/approvals`, `/receipts`, `/bundle` | Mission-scoped reads |
| — | `/api/v1/approvals`, `/api/v1/receipts` | Create/list/decide approvals; create/get receipts |
| GET | `/api/v1/updates/stream` | SSE (see `app/api/routes/updates.py`) |

**PARTIAL:** Database models for workers, integrations, and cost events exist; dedicated REST surfaces for those domains may lag the schema—see root `STATUS.md`.

## Rules

- **`POST /api/v1/commands`**: every call creates a **mission** and a **mission_event** (`event_type=created`). No exceptions.
- **`POST /api/v1/intake`**: interpretation first; only **mission_request** / **mission_followup** outcomes create missions (same `CommandService` path as `/commands` when they do).
- Use **async** SQLAlchemy sessions and async route handlers throughout.
