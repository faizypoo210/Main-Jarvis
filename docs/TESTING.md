# Testing — Control Plane (pytest)

This repo’s **authoritative** HTTP API is `services/control-plane` (FastAPI + PostgreSQL + Alembic). Automated tests use **pytest**, **httpx** (async ASGI client), and a **disposable PostgreSQL** database — the same dialect and driver as production (`asyncpg`), not SQLite.

## Prerequisites

- **Python 3.11+** (match CI).
- **PostgreSQL** reachable from your machine (local install, Docker, or the stack from `jarvis.ps1`).
- A **dedicated empty database** for tests (data is truncated between tests; migrations run once per session).

## Environment variables

| Variable | Purpose |
|----------|---------|
| `PYTEST_CONTROL_PLANE_DATABASE_URL` | **Optional.** Full async SQLAlchemy URL for the test database. If unset, defaults to `postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/jarvis_cp_test`. |
| `PYTEST_CONTROL_PLANE_API_KEY` | **Optional.** API key expected by `x-api-key` on protected routes. Default: `pytest-control-plane-api-key`. |
| `SECRET_KEY` | Set automatically in tests if missing (`pytest` default). |

Tests **overwrite** `DATABASE_URL` for the pytest process to match `PYTEST_CONTROL_PLANE_DATABASE_URL` (or the default above), so your normal `services/control-plane/.env` does not accidentally point pytest at a dev database.

**Create the database once** (example for local Postgres):

```sql
CREATE DATABASE jarvis_cp_test;
```

Docker (ephemeral, matches CI defaults):

```powershell
docker run --name jarvis-cp-test-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=jarvis_cp_test -p 5432:5432 -d postgres:16
```

## Commands

From the control plane package:

```powershell
cd F:\Jarvis\services\control-plane
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -v
```

**Fast unit tests** (schemas + shared readiness helpers + registry summary mocks — no Alembic, no live DB for the test body):

```powershell
cd F:\Jarvis\services\control-plane
python -m pytest -m unit -q
```

**Integration / contract tests** (HTTP + PostgreSQL + Alembic — same as CI):

```powershell
cd F:\Jarvis\services\control-plane
python -m pytest -m integration -v
```

Or use the helper (repo root — full suite including integration):

```powershell
cd F:\Jarvis
.\scripts\20-run-control-plane-tests.ps1
```

Unit-only helper:

```powershell
cd F:\Jarvis
.\scripts\21-run-control-plane-unit-tests.ps1
```

### Command Center (frontend)

From `services/command-center`:

```powershell
npm ci
npm run test
npm run build
```

Vitest + Testing Library cover a few high-value shell/runtime behaviors; production verification remains `npm run build`.

**SSE live updates:** In dev, Command Center uses Vite’s `/api` proxy, which injects `x-api-key` from `CONTROL_PLANE_API_KEY`. The stream sends periodic `: keepalive` comment lines; if that key does not match the control plane, REST can look fine while `/api/v1/updates/stream` returns 401.

### Run a subset

```powershell
cd F:\Jarvis\services\control-plane
python -m pytest tests/test_api_contracts.py::test_health_ok -v
```

### What is real vs external

- **Real:** HTTP routes, SQLAlchemy persistence, Alembic schema, mission/events/approvals/receipts/operator inbox derivation for the flows under test.
- **Not exercised:** GitHub/Gmail **vendor** APIs (governed routes only create **pending** approvals and timeline rows until a human approves — no outbound GitHub call in these tests).
- **Redis:** Command intake skips Redis publish when `context` uses `rehearsal_mode: synthetic_api_only` and `skip_runtime_publish: true` (same pattern as golden-path scripts).

## CI

GitHub Actions runs the same suite against a **PostgreSQL 16** service container and builds **Command Center** (`npm ci` + `npm run build`). See `.github/workflows/ci.yml`.

## Implementation notes

- **PostgreSQL + asyncpg** — Same driver/dialect as production; SQLite is not a drop-in substitute for these tests.
- **Event loop** — `pytest.ini` uses **session-scoped** asyncio loops (`asyncio_default_fixture_loop_scope` / `asyncio_default_test_loop_scope`) so `httpx` ASGITransport, SQLAlchemy’s async engine, and asyncpg share one loop (required on Windows and with connection pooling).
- **`CONTROL_PLANE_TESTING=1`** — Set in `tests/conftest.py` so the app lifespan skips `engine.dispose()` between ASGI client sessions while still matching production shutdown when the flag is unset.

## Troubleshooting

- **`password authentication failed for user "postgres"`** — Point `PYTEST_CONTROL_PLANE_DATABASE_URL` at credentials that exist on your Postgres instance (your `services/control-plane/.env` may use a different user/password than the CI default).
- **`database "jarvis_cp_test" does not exist`** — Create the database or set `PYTEST_CONTROL_PLANE_DATABASE_URL` to an existing empty database.
- **`got Future ... attached to a different loop`** — Ensure you are not overriding `pytest.ini` asyncio settings; session-scoped loops are intentional.
- **Schema drift (`UndefinedColumnError`, `UndefinedTableError`, missing `workers.instance_id`, missing `heartbeat_findings`, etc.)** — The live database is behind Alembic. With `DATABASE_URL` pointing at that database:

  ```powershell
  cd F:\Jarvis\services\control-plane
  python -m alembic upgrade head
  ```

  Production/dev control plane startup also runs a **schema guard** (skipped when `CONTROL_PLANE_TESTING=1` in pytest). For emergency local debugging only, `CONTROL_PLANE_SKIP_SCHEMA_CHECK=1` disables the guard (not recommended for real deployments).
